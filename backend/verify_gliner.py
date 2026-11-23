import sys
import time

# 1. Check Import & Version
try:
    import gliner
    import torch
    from gliner import GLiNER

    installed_version = getattr(gliner, "__version__", "unknown")
    print(f"[1] GLiNER import successful. Installed version: {installed_version}")
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    sys.exit(1)

# 2. Check CUDA / Hardware Availability
cuda_available = torch.cuda.is_available()
device_name = torch.cuda.get_device_name(0) if cuda_available else "CPU"
print(f"[2] Hardware acceleration: CUDA available = {cuda_available} ({device_name})")

# 3. Model Local Download & Load Verification
model_id = "urchade/gliner_multi_pii-v1"
print(f"[3] Downloading/loading '{model_id}' from Hugging Face locally...")

start_time = time.perf_counter()
try:
    model = GLiNER.from_pretrained(model_id)
    if cuda_available:
        model = model.to("cuda")
    elapsed_time = time.perf_counter() - start_time
    load_success = True
    error_msg = None
except Exception as e:
    elapsed_time = time.perf_counter() - start_time
    load_success = False
    error_msg = str(e)

# 4. Report Results
print("\n" + "=" * 40)
print("VERIFICATION REPORT")
print("=" * 40)
print(f"GLiNER Version:            {installed_version}")
print(f"Model Loaded Successfully: {load_success}")
print(f"Approximate Load Time:     {elapsed_time:.2f} seconds")
print(f"CUDA/GPU Available:        {cuda_available} ({device_name})")
print(f"Errors:                    {error_msg if error_msg else 'None'}")
print("=" * 40)