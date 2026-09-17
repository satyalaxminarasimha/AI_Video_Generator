# Optional image-to-video workflows

The application supports an optional local ComfyUI adapter through `I2V_ENABLED=1`.
ComfyUI workflows differ by installed model/custom nodes, so export your own API
workflow JSON here as `i2v_workflow.json` and use these placeholders where needed:

- `{image}` input image path
- `{prompt}` motion prompt
- `{duration}` requested clip duration
- `{output}` desired output path

The normal renderer works without ComfyUI.
