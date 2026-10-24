# Image pipeline: how to get better pictures

Research notes (October 2026) on the ComfyUI path behind `/imagine`, Cave's `generate_image` tool, `/portrait` and `/poster`.
Nothing here has been measured on our GPU yet. The experiment plan at the end turns the guesses into numbers.

**Current setup:** `utils/image_gen.py` submits `utils/image_z_image_turbo.json` to ComfyUI Desktop on the gaming PC (RTX 3080 10 GB, 32 GB RAM, models on NVMe).
The models are Z-Image Turbo `z_image_turbo_int8_convrot.safetensors` (6.2 GB), `qwen_3_4b_fp8_mixed.safetensors` (5.6 GB) and `ae.safetensors`, all from [Comfy-Org/z_image_turbo](https://huggingface.co/Comfy-Org/z_image_turbo).
`services/image_service.py` unloads Ollama first and calls `/free` afterwards, so every job is a cold load. A job takes about 20–30 s.

## Status (2026-10-24)

Done and measured on the 3080 (local runs, Ollama unloaded): items 1-5 of the ranked list, plus FLUX.2 [klein] 4B as the experimental `/imagine model:` choice.
- Z-Image Turbo at 8 steps / CFG 1 / 1024²: about 12 s cold and 7 s warm, faster than the old 9 steps / CFG 1.5 / 768².
- FLUX.2 klein 4B fp8 (`black-forest-labs/FLUX.2-klein-4b-fp8`, 4.07 GB, Apache 2.0): 4 steps, about 9 s cold and 4 s warm. It runs on Z-Image's `qwen_3_4b_fp8_mixed` encoder (same base model), so the 8 GB `qwen_3_4b` download isn't needed; only `flux2-vae.safetensors` (0.34 GB) was added. Strong lighting; its on-image lettering is often gibberish.
- End to end through the bot service (enhancer, safety check, GPU handoff, cold load): 14-25 s per image.

**FLUX.3 [klein] added (2026-10-24)** as `/imagine model: flux3-klein`: int8 diffusion (5.83 GB) + `qwen3vl_4b_int8_convrot` encoder (4.86 GB) + the shared `flux2-vae`, 16 steps, about 15 s per image when switching models. In a 3-way A/B (photoreal, watercolour, anime) it gave the most detail and the best watercolour. The optional 9B prompt upsampler from the template is skipped (Cave's enhancer does that job).

Originally Missed in the research:** FLUX.3 [klein] (`black-forest-labs/flux-3-image-klein-comfy`, published 2026-10-14) has an official int8 ConvRot build (5.8 GB diffusion + 4.9 GB `qwen3vl_4b` encoder) and ComfyUI v0.41 already has its nodes. It is gated (accept the licence on Hugging Face while logged in) under a non-Apache "other" licence, so it needs the owner's click before it can be tried. It's the next candidate for the `model:` choice.

## TL;DR: the top 3

1. **Match the official workflow: CFG 1, 8 steps, 1024².** This is a JSON-only change with no downloads. We run CFG 1.5 at 768², the official template runs CFG 1 at 1024². At CFG 1, ComfyUI skips the second (negative) model pass, which should roughly pay for the 1.78× extra pixels.
2. **Rewrite `enhance_image_prompt` to the official Z-Image prompt-enhancer rules.** That means concrete, objective, natural-language description, with no "8k, masterpiece" tags, the user's subject and details kept exactly, and on-image text in double quotes. Our current instructions ask for the opposite. Also stop the enhancer from rewriting the fixed `/portrait` and `/poster` templates.
3. **Pick the size per job.** Posters should be tall and `/imagine` should allow wide/tall, all at about 1 MP. Today every job is a 768² square.

Everything else (LoRAs, upscaling, a different model) is second-order until 1–3 are done and measured.

---

## 1. Workflow settings: what we use vs what's recommended

| Setting | Ours (`image_z_image_turbo.json`) | Official Comfy template ([`image_z_image_turbo_int8.json`](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_z_image_turbo_int8.json), the same three files we use) | Notes |
|---|---|---|---|
| Steps | 9 | **8** | Turbo is distilled for 8 model evaluations. The [model card](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)'s `num_inference_steps=9` is a Diffusers counting quirk that "results in 8 DiT forwards". In ComfyUI 8 is the right number. Community guides report that going much higher adds artifacts. |
| CFG | 1.5 | **1** | The model card says "Guidance should be 0 for the Turbo models", which is CFG 1 in ComfyUI. Any CFG ≠ 1 makes ComfyUI also run the negative (here a `ConditioningZeroOut`) every step, which nearly doubles sampling cost for no real benefit. Community claims put the safe range at 1–2 and say 4+ oversaturates. |
| Sampler / scheduler | res_multistep / simple | res_multistep / simple | ✅ Same. `euler`/`simple` is the common alternative (community). |
| Shift (`ModelSamplingAuraFlow`) | 3 | 3 | ✅ Same. |
| Resolution | 768×768 | **1024×1024** | Base Z-Image is trained for 512²–2048² total area at any aspect ratio. Community reports put Turbo's sweet spot at ~1–2 MP and say 2K+ in one pass starts to distort. |
| Negative prompt | zeroed-out conditioning | zeroed-out conditioning | At CFG 1 there is effectively **no negative prompt**. Turbo doesn't support CFG, so phrase every constraint positively (see §2). |

**Quick wins needing no new models** (all in the JSON or `image_gen.py`):
- `cfg: 1`, `steps: 8`, and width/height of 1024 (or the per-job aspect ratios in §5).
- Leave seed randomisation as it is (`image_gen.py` sets a random seed; keep it under 17 digits).

Expected time: the CFG change cuts sampler time roughly in half and 1024² adds ~1.8× the pixels, so total time should land near today's. That is a guess. Measure it with experiment A.

## 2. Prompting

**What the model wants.** Z-Image uses a Qwen3-4B LLM as its text encoder and was trained on natural-language captions (English and Chinese). The official prompt enhancer ([`pe.py` in the Tongyi-MAI/Z-Image-Turbo Space](https://huggingface.co/spaces/Tongyi-MAI/Z-Image-Turbo/blob/main/pe.py)) asks for:
1. Lock the core elements: subject, quantity, action, state, named IPs, colours, any requested text.
2. If the request implies a design or a solution, work out a concrete, visualisable version first, then describe that.
3. Enrich with composition, lighting, materials, colour scheme and spatial layering.
4. Put all on-image text verbatim in English double quotes, with position, size, font and material.
5. Be objective and concrete. **No metaphors or emotional language, no meta tags like "8K", no drawing instructions.** Output only the final prompt.

Community guides (not official) agree on sentences rather than tag lists, a **sweet spot around 80–180 words**, no `(word:1.3)` weighting (unsupported), and "say what you want, not what you don't" (no CFG means no negative prompt).

**What our enhancer does today** (`utils/ai_handler.py`, `enhance_image_prompt`):
- It tells the 12B model to write a prompt "suitable for Stable Diffusion/Flux" (and calls the encoder "quen3-4B").
- Its only example ends with `8k resolution, photorealistic`. That is exactly the meta-tag style `pe.py` bans, and it nudges every image toward photorealism even when the user asked for a cartoon.
- It has no length guidance and doesn't tell the model to keep the user's specifics or quote requested text.

**Recommended enhancer instructions** (keep the safety check exactly as it is, and change only the "ENHANCE" half and the example):
- "Rewrite the request as one paragraph of plain English, 60–150 words, describing the image concretely: main subject first (keep every subject, count, colour, name and detail the user gave), then setting, composition and camera/framing, lighting, materials, colour palette, and the medium/style (photo, oil painting, 3D render, cartoon...). If the user named a style, keep it; if not, pick one that suits the idea, not always a photo."
- "If the image should contain words, write them in double quotes and say where they appear. Otherwise don't add any text."
- "No quality tags (8k, masterpiece, best quality, ultra-detailed), no weights or brackets, no metaphors, no 'don't include X'. Output only the prompt."
- Replace the example with one in that style. For "A dog": *"A golden retriever mid-leap catching a red frisbee in a sunlit city park, photographed from a low angle with a telephoto lens. Late-afternoon golden light rims its fur, ... shallow depth of field blurs the green trees and a wooden bench behind it."*

**Fixed templates (`/portrait`, `/poster`).** Both build a careful prompt and then send it through the same free-form enhancer in `ImageService.generate`, which can drop "plain light grey background", "centered face" or "no text" and move the composition.
- Recommended: add a `enhance=False` (safety check only) path to `ImageService.generate` for these, and write the templates themselves in the `pe.py` style.
- `/poster` only interpolates the user's `topic`. Keep the safety check on that, but don't rewrite the template.
- Phrase things positively. "No text" in a positive prompt can *invite* lettering. Instead, describe the lower fifth as "a plain dark band of solid colour along the bottom", where Pillow draws the slogan.
- Make the poster tall (§5), since `poster_caption` handles any size.
- Experiment E: Z-Image is one of the stronger open models at rendering short English text. Try asking it for the slogan itself in quotes, with the Pillow overlay kept as the fallback.

**Message length.** A 150-word enhanced prompt is ~900 characters, and `image_success` in `content/dialogue.json` echoes both `{prompt}` and `{enhanced_prompt}`. A long `/imagine` prompt could push the message past Discord's 2000-character limit, so truncate the echoed text (for example 300 + 900 characters) when the enhancer changes.

## 3. Model options (10 GB VRAM, 32 GB RAM, cold load every job)

| Option | Fits 3080? | Licence | Verdict |
|---|---|---|---|
| **Z-Image Turbo int8_convrot** (current) | ✅ 6.2 GB + 5.6 GB TE (swapped in turn) | Apache 2.0 | **Keep.** It is the official Comfy int8 build. Int8 tensor cores exist on Ampere, and community reports put int8 at ~1.5–2× faster than bf16/fp8 on a 3090. There is no newer Turbo checkpoint. |
| Z-Image Turbo `nvfp4` (4.5 GB) / `qwen_3_4b_fp4_mixed` TE (3.5 GB) | ❌ in practice | Apache 2.0 | FP4 needs Blackwell (RTX 50) hardware. On a 3080 there's no speed-up and it's a quality risk. Not viable. |
| Z-Image (base, Jan 2026, [Tongyi-MAI/Z-Image](https://huggingface.co/Tongyi-MAI/Z-Image)) | ✅ similar size | Apache 2.0 | 50 steps + CFG means ~6× slower. More diverse, has real negative prompts, but rated lower for visual quality than Turbo. It's meant for fine-tuning and LoRA training, not serving. Skip. |
| Z-Image-Edit / Omni-Base | — | — | Still "to be released" in the official repo as of this writing. Watch it: it would give img2img editing in the same family. |
| **FLUX.2 [klein] 4B** (distilled), `black-forest-labs/FLUX.2-klein-4b-fp8` → `flux-2-klein-4b-fp8.safetensors`, plus `Comfy-Org/flux2-klein-4B` TE `qwen_3_4b.safetensors` (8.0 GB) and `Comfy-Org/flux2-dev` VAE `flux2-vae.safetensors` | ✅ BFL quotes ~8.4 GB at 4 steps | Apache 2.0 | **The only alternative worth testing.** 4 steps, and it also does reference-image editing in one model. FP8 isn't accelerated on Ampere (it saves memory, not time). BFL claims it beats Z-Image, but that is vendor data. The only independent comparison found favours Z-Image for realism and text. Download is roughly 4 GB diffusion + 8 GB TE + VAE (exact sizes on the repo pages). Test it as a side-by-side (experiment D), don't switch blind. |
| FLUX.2 [klein] 9B | ❌ (~19.6 GB distilled) | Non-commercial | Skip. |
| Krea 2 Turbo (June 2026, 12B) int8 ConvRot (14.1 GB) | ❌ needs offloading + the ComfyUI-INT8-Fast custom node | Krea 2 Community Licence | Skip on 10 GB. Revisit with a bigger card. |
| Qwen-Image 2.x (Sep 2026: 2.1, unified gen+edit) | ❌ / tight (Q8/GGUF territory) | Varies by version | Best open text rendering, but the slowest. One blog reports 2.1 leads the open-weight arena (unverified). Watch list only. |

**LoRAs.**
- Z-Image Turbo LoRAs exist on Civitai and Hugging Face (filter by base model "ZImageTurbo"). No specific retro-propaganda-poster LoRA could be confirmed.
- Two caveats:
  - LoRAs trained directly on Turbo can lose the 8-step speed and come out blurry. DiffSynth-Studio's [Z-Image-Turbo-DistillPatch](https://huggingface.co/DiffSynth-Studio/Z-Image-Turbo-DistillPatch) exists to fix that, so prefer LoRAs that say they work at 8 steps / CFG 1.
  - It's **unconfirmed whether stock ComfyUI applies a LoRA on top of the int8_convrot weights**. Other ConvRot models point to the third-party ComfyUI-INT8-Fast node pack for LoRAs. Try one LoRA with `LoraLoaderModelOnly` (experiment F) before planning around it.
- A style LoRA is the right tool for the poster look *if* that works, but a good template prompt may get most of the way there for free.

**Seed diversity.** Turbo's distillation makes different seeds give near-identical compositions (the model card rates its diversity "low"). For "give me another one", vary the prompt (the enhancer at a higher temperature, or a different framing), not just the seed. Community fixes exist (the SeedVarianceEnhancer node, an "SDA" diversity LoRA), but their own authors warn about artifacts. Not worth it for a Discord bot.

## 4. Pipeline additions

| Addition | Effort | Expected gain | Cost | Recommendation |
|---|---|---|---|---|
| Native 1024² / ~1 MP aspect ratios | S | High (detail, framing) | ~same time if CFG=1 | **Do** (§1, §5) |
| Hires fix: latent upscale ×1.5, second `KSampler` 4–8 steps, denoise ~0.3–0.4 | M | Medium at full size. Discord previews are small. | +60–100% time, more VRAM at ~2.3 MP | Optional `/imagine hd:true` later. Community reports say a plain latent upscale + resample works with Turbo, but model-upscale-then-latent caused issues. The 0.3–0.4 denoise is a starting guess. |
| ESRGAN-style model upscale (e.g. a 4× model, ~65 MB) | S | Low | +2–5 s | Skip. It sharpens without adding real detail, and Discord recompresses anyway. |
| Face detailer (Impact Pack `FaceDetailer` + a YOLO face model) | M (custom nodes) | Low for badges | +5–10 s | Skip. Badge headshots fill the frame at 1024², and detailers help small faces. Revisit only if faces look bad in experiment C. |
| Negative prompt | — | None at CFG 1 | — | Not supported on Turbo. Use positive phrasing. |
| img2img (`LoadImage` → `VAEEncode` → `KSampler` denoise 0.5–0.8) | M | New feature, not quality | ~same | Possible later ("restyle this attachment"). Z-Image Turbo can do it, but a proper editor (Klein 4B / Z-Image-Edit) is better. **Never on users' avatars by default:** `/portrait` deliberately puts nothing about the person into the prompt. |
| Text encoder on CPU (`CLIPLoader device: cpu`) | S | Maybe faster (no TE↔DiT VRAM swap) | Encoding takes a few s on CPU, uses ~6 GB RAM | Try in experiment A. Possibly a speed win, not quality. |

## 5. Bot code that limits quality

- **Resolution is hard-coded** (768² in the JSON) and there's no aspect option. Suggested sizes are 1024×1024, 1216×832 / 832×1216 (landscape/tall), 1344×768 (wide), all ~1 MP. Change `image_gen.generate_image(prompt, width=1024, height=1024)` to set node 41. `/poster` should use 832×1216, `/portrait` 1024² (it is cropped square), and `/imagine` should get an optional `shape:` choice. Cave's tool could pick a shape too, but keep its schema small.
- **Steps and CFG are only in the JSON.** Fine as is, but set them to 8 / 1.
- **The enhancer** has the wrong model-family guidance and meta tags (§2), and it rewrites the fixed templates.
- **Prompt length:** the agent tool truncates the raw prompt to 500 characters, which is fine. The enhanced prompt has no cap. Qwen-based Z-Image pipelines typically take up to ~512 tokens, so 150 words is well within budget. Cap the *echo* in `image_success` (§2), not the prompt.
- **Timeouts:** `GENERATION_TIMEOUT = 300` s of websocket *silence* in `image_gen.py`. `CLAUDE.md` still says 180 s, so update it. Silence-based is right because sampling sends progress messages. 300 s only matters for a cold load from a slow disk, so leave it. If hires fix is added, still nothing to change.
- **One-job lock + `/free` after every job:** correct for a 10 GB card shared with Ollama. The price is a cold load each time (NVMe and the OS file cache keep it to seconds). Don't try to keep ComfyUI warm unless Ollama moves off this GPU.
- **Small things:**
  - `queue_prompt`, `get_history` and `get_image` have no `urlopen` timeout. A hung ComfyUI HTTP call would hold the lock forever. Add `timeout=30`.
  - The enhancer runs the 12B model *before* unloading, which is correct, since it needs the chat model.

## 6. Ranked change list

| # | Change | Effort | Expected gain | VRAM / time | Downloads |
|---|---|---|---|---|---|
| 1 | Workflow JSON → `cfg 1`, `steps 8`, 1024² | XS | High (sharper, more detail, official settings) | Same VRAM, ≈ same time (measure) | None |
| 2 | Rewrite `enhance_image_prompt` to `pe.py` rules, 60–150 words, no meta tags, quoted text | S | High (prompt adherence, style variety) | None | None |
| 3 | Per-job size: `/poster` tall, `/imagine shape:` | S | Medium–high (composition) | ~1 MP each | None |
| 4 | `/portrait` & `/poster` skip enhancement (safety check only), positive phrasing, empty bottom band | S | Medium (consistent look, text-free band) | None | None |
| 5 | Truncate the echoed prompts in `image_success`, plus HTTP timeouts in `image_gen.py` | XS | Robustness | None | None |
| 6 | Try Z-Image rendering the poster slogan itself | S | Medium (looks native) | None | None |
| 7 | Side-by-side test of FLUX.2 klein 4B | M | Unknown (vendor says better) | ~8 GB, 4 steps | ~4 GB fp8 model + 8 GB TE + VAE (exact files in §3) |
| 8 | Optional hires-fix second pass (`hd:true`) | M | Medium at full size only | +60–100% time | None |
| 9 | Style LoRA for posters (only if experiment F shows LoRAs work on int8) | M | Medium for posters | Small | A LoRA, typically 50–300 MB |

## 7. Experiment plan (when the GPU is free)

Run every test in ComfyUI Desktop directly, with the bot's job lock not involved. Keep Ollama unloaded and do it all in one sitting so the cache state is comparable.

**Prompt set (8 prompts, fixed seeds 1–4 each):**
1. "a golden retriever catching a frisbee in a park" (photo, motion)
2. "a caricature of a smartphone looking awkward" (cartoon, today's default prompt)
3. "a cozy cyberpunk ramen stall at night in the rain" (lighting, detail)
4. "an oil painting of a lighthouse in a storm" (non-photo style)
5. the `/portrait` template with two archetypes (faces, consistency)
6. the `/poster` template with topics "cake" and "testing" (style, empty band)
7. "a neon sign that says \"OPEN 24 HOURS\" above a diner door" (text rendering)
8. a raw, short user prompt *and* its enhanced version from the new enhancer (enhancer effect)

**Experiments:**
- **A. Settings** (no downloads): current (9 steps, CFG 1.5, 768²) vs official (8, CFG 1, 1024²) vs 8, CFG 1, 768² (isolates resolution). Optionally add TE on CPU. Record wall time (cold load and warm, from ComfyUI's console "Prompt executed in X s") and peak VRAM (Task Manager → GPU → dedicated memory).
- **B. Enhancer:** for prompts 1–4 and 8, old enhancer vs new instructions (run `enhance_image_prompt` against the real 12B model with a scratch script; no bot changes needed). Generate both with the A winner.
- **C. Portraits:** the `/portrait` template enhanced vs not enhanced, 4 seeds × 2 archetypes. Judge consistency of framing, background and face quality.
- **D. Klein 4B:** same prompts, 4 steps, its template settings vs the A winner. Judge quality, text, time and cold load.
- **E. Poster text:** the `/poster` template asking for `the words "SCIENCE WAITS FOR NO ONE"` in the bottom band vs an empty band + Pillow.
- **F. LoRA on int8:** one Z-Image-Turbo style LoRA through `LoraLoaderModelOnly` at strength 0.8. Check it changes the output vs strength 0, with no error and no blur.

**How to judge:**
- Put each prompt's variants side by side (same seed) in a grid. Score 1–5 on **prompt adherence** (did it show what was asked: count, colours, style), **quality** (artifacts, hands, faces) and **fit for purpose** (does the poster look like a poster).
- Two people score blind if possible (a friend in the Discord, without telling them which is which).
- Adopt a change if it wins or ties on quality, wins on adherence in ≥ 5 of 8 prompts, and keeps the job under ~35 s cold.

## Sources

Official:
- [Tongyi-MAI/Z-Image-Turbo model card](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) (steps, "guidance should be 0", Apache 2.0)
- [Tongyi-MAI/Z-Image GitHub](https://github.com/Tongyi-MAI/Z-Image) (model zoo, base/edit/omni status, resolution range)
- [Official prompt enhancer `pe.py`](https://huggingface.co/spaces/Tongyi-MAI/Z-Image-Turbo/blob/main/pe.py)
- [Comfy-Org workflow templates](https://github.com/Comfy-Org/workflow_templates/tree/main/templates) (`image_z_image_turbo.json`, `image_z_image_turbo_int8.json`)
- [Comfy-Org/z_image_turbo files](https://huggingface.co/Comfy-Org/z_image_turbo/tree/main/split_files)
- [ComfyUI FLUX.2 klein docs](https://docs.comfy.org/tutorials/flux/flux-2-klein)
- [BFL klein announcement](https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence)
- [DiffSynth-Studio Z-Image-Turbo-DistillPatch](https://huggingface.co/DiffSynth-Studio/Z-Image-Turbo-DistillPatch)

Community (treat as claims):
- [aistudynow Z-Image Turbo settings](https://aistudynow.com/z-image-turbo-settings-you-must-change-this-for-best-quality/)
- [Diffusion Doodles on Z-Image Turbo](https://diffusiondoodles.substack.com/p/z-image-turbo-fast-and-functional)
- [Qubrid prompt guide](https://www.qubrid.com/blog-news/how-to-write-better-prompts-for-z-image-turbo)
- [Z-Image-Turbo INT8 on a 3090](https://huggingface.co/bertbobson/Z-Image-Turbo-INT8-Tensorwise/blob/main/README.md)
- [Z-Image-Turbo W4A8 timings](https://huggingface.co/CuTIsolation/Z-Image-Turbo-W4A8)
- [Krea 2 INT8 ConvRot](https://huggingface.co/ocyou/Krea2-INT8-ConvRot)
- [Decrypt: Z-Image vs Flux](https://decrypt.co/350572/chinas-z-image-dethrones-flux-king-of-ai-art)
- [Apatero on seed variance](https://apatero.com/blog/seedvarianceenhancer-z-image-diversity-complete-guide-2025)
- [buildfastwithai on open models, 2026](https://www.buildfastwithai.com/blogs/ideogram-4-open-weight-image-model)
