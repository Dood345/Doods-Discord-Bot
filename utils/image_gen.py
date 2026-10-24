import json
import urllib.request
import urllib.parse
import websocket # requires: pip install websocket-client
import uuid
import random
import logging
from config import BotConfig

logger = logging.getLogger(__name__)

# The IP of your ComfyUI machine
COMFY_URL = BotConfig.COMFY_URL
CLIENT_ID = str(uuid.uuid4())
GENERATION_TIMEOUT = 300  # seconds of websocket silence before giving up (a cold model load sends nothing)
HTTP_TIMEOUT = 30  # ComfyUI's HTTP calls; a hung one would otherwise hold the one-job lock forever

# Each generator: its API-format workflow and which nodes take the prompt, seed and size
MODELS = {
    "z-image": {"workflow": "utils/image_z_image_turbo.json", "prompt": ("45", "text"),
                "seed": ("44", "seed"), "size": ["41"], "label": "Z-Image Turbo"},
    # Experimental: FLUX.2 [klein] 4B distilled (fp8, 4 steps); shares Z-Image's Qwen3-4B text encoder
    "flux2-klein": {"workflow": "utils/image_flux2_klein.json", "prompt": ("4", "text"),
                    "seed": ("9", "noise_seed"), "size": ["8", "10"], "label": "FLUX.2 klein (experimental)"},
    # Experimental: FLUX.3 [klein] distilled int8 (gated repo black-forest-labs/flux-3-image-klein-comfy, 16 steps)
    "flux3-klein": {"workflow": "utils/image_flux3_klein.json", "prompt": ("4", "text"),
                    "seed": ("7", "seed"), "size": ["6"], "label": "FLUX.3 klein (experimental)"},
}
DEFAULT_MODEL = "z-image"
# ~1 megapixel shapes (both models were trained around 1 MP; sides are multiples of 64)
SHAPES = {"square": (1024, 1024), "tall": (832, 1216), "wide": (1216, 832), "banner": (1344, 768)}

def is_comfy_online():
    """Fast check to see if ComfyUI is running"""
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=1.0) as response:
            return response.status == 200
    except Exception:
        return False

def free_comfy_memory():
    """Ask ComfyUI to drop its models from VRAM/RAM, so Ollama gets the GPU back after an image."""
    try:
        req = urllib.request.Request(f"{COMFY_URL}/free", data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).close()
    except Exception as e:
        logger.warning(f"Couldn't free ComfyUI memory: {e}")

def queue_prompt(prompt_workflow):
    p = {"prompt": prompt_workflow, "client_id": CLIENT_ID}
    data = json.dumps(p).encode('utf-8')
    try:
        req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req, timeout=HTTP_TIMEOUT).read())
    except Exception as e:
        logger.error(f"Failed to queue prompt: {e}")
        return None

def get_history(prompt_id):
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read())
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return None

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/view?{url_values}", timeout=HTTP_TIMEOUT) as response:
            return response.read()
    except Exception as e:
        logger.error(f"Failed to get image: {e}")
        return None

def build_workflow(user_prompt, width=1024, height=1024, model=DEFAULT_MODEL):
    """The model's workflow with the prompt, a random seed and the size filled in (None if it's broken)."""
    spec = MODELS[model]
    try:
        with open(spec["workflow"], "r", encoding="utf-8") as f:
            workflow = json.load(f)
    except FileNotFoundError:
        logger.error(f"Workflow file {spec['workflow']!r} not found!")
        return None
    node, field = spec["prompt"]
    if node not in workflow:
        logger.error(f"Prompt node {node} not found in {spec['workflow']}")
        return None
    workflow[node]["inputs"][field] = user_prompt
    node, field = spec["seed"]
    workflow[node]["inputs"][field] = random.randint(1, 100000000000000)
    for node in spec["size"]:
        workflow[node]["inputs"].update(width=int(width), height=int(height))
    return workflow

def generate_image(user_prompt, width=1024, height=1024, model=DEFAULT_MODEL):
    logger.info(f"Starting image generation ({model}, {width}x{height}) for prompt: {user_prompt}")
    workflow = build_workflow(user_prompt, width, height, model)
    if workflow is None:
        return None

    # Connect to the WebSocket to listen for completion
    # Timeout so a stalled ComfyUI can't hang the executor thread (and the GPU lock) forever
    ws = websocket.WebSocket()
    ws.settimeout(GENERATION_TIMEOUT)
    try:
        ws_url = COMFY_URL.replace("http://", "ws://").replace("https://", "wss://") + f"/ws?clientId={CLIENT_ID}"
        ws.connect(ws_url)
    except Exception as e:
        logger.error(f"Failed to connect to ComfyUI WebSocket at {ws_url}: {e}")
        return None

    # Send the workflow
    response = queue_prompt(workflow)
    if not response or 'prompt_id' not in response:
        logger.error("Failed to get prompt_id from ComfyUI")
        ws.close()
        return None

    prompt_id = response['prompt_id']
    logger.info(f"Prompt queued with ID: {prompt_id}")

    # Wait for completion
    try:
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break # Execution finished!
    except Exception as e:
        logger.error(f"WebSocket error during generation: {e}")
        ws.close()
        return None

    ws.close()

    # Fetch the result
    history_data = get_history(prompt_id)
    if not history_data or prompt_id not in history_data:
        logger.error("No history found for prompt_id")
        return None

    history = history_data[prompt_id]
    if 'outputs' in history:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    return image_data # Returns raw bytes

    logger.error("No images found in output")
    return None
