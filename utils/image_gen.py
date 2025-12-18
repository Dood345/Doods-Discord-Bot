import json
import urllib.request
import urllib.parse
import websocket # requires: pip install websocket-client
import uuid
import random
import logging
import time
from config import BotConfig

logger = logging.getLogger(__name__)

# The IP of your ComfyUI machine
COMFY_URL = BotConfig.COMFY_URL
CLIENT_ID = str(uuid.uuid4())

def is_comfy_online():
    """Fast check to see if ComfyUI is running"""
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=1.0) as response:
            return response.status == 200
    except Exception:
        return False

def queue_prompt(prompt_workflow):
    p = {"prompt": prompt_workflow, "client_id": CLIENT_ID}
    data = json.dumps(p).encode('utf-8')
    try:
        req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())
    except Exception as e:
        logger.error(f"Failed to queue prompt: {e}")
        return None

def get_history(prompt_id):
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}") as response:
            return json.loads(response.read())
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return None

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    try:
        with urllib.request.urlopen(f"{COMFY_URL}/view?{url_values}") as response:
            return response.read()
    except Exception as e:
        logger.error(f"Failed to get image: {e}")
        return None

def generate_image(user_prompt):
    logger.info(f"Starting image generation for prompt: {user_prompt}")
    
    # 1. Load the template
    try:
        with open("utils/zImageGGUF.json", "r", encoding="utf-8") as f:
            workflow = json.load(f)
    except FileNotFoundError:
        logger.error("Workflow file 'utils/zImageGGUF.json' not found!")
        return None

    # 2. Inject the prompt
    # Node 8 is CLIP Text Encode (Positive Prompt)
    if "8" in workflow and "inputs" in workflow["8"]:
        workflow["8"]["inputs"]["text"] = user_prompt
    else:
        logger.error("Node 8 (Positive Prompt) not found in workflow!")
        return None
    
    # Node 10 is KSampler - randomize seed
    if "10" in workflow and "inputs" in workflow["10"]:
        workflow["10"]["inputs"]["seed"] = random.randint(1, 100000000000000)

    # 3. Connect to WebSocket to listen for completion
    ws = websocket.WebSocket()
    try:
        ws_url = COMFY_URL.replace("http://", "ws://").replace("https://", "wss://") + f"/ws?clientId={CLIENT_ID}"
        ws.connect(ws_url)
    except Exception as e:
        logger.error(f"Failed to connect to ComfyUI WebSocket at {ws_url}: {e}")
        return None
    
    # 4. Send the workflow
    response = queue_prompt(workflow)
    if not response or 'prompt_id' not in response:
        logger.error("Failed to get prompt_id from ComfyUI")
        ws.close()
        return None
        
    prompt_id = response['prompt_id']
    logger.info(f"Prompt queued with ID: {prompt_id}")
    
    # 5. Wait for completion
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

    # 6. Fetch the result filename
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
