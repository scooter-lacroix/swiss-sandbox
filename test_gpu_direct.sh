#!/bin/bash

echo "🔍 TESTING GPU SELECTION FOR MANIM..."

# Test 1: Force discrete GPU selection
echo "Test 1: Forcing RX 7900 XT/XTX (GPU 0)"
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json
export MESA_VK_DEVICE_SELECT=0
export DRI_PRIME=0
export AMD_VULKAN_ICD=RADV

echo "Before test - GPU status:"
rocm-smi --showuse --csv

echo "Starting render test..."
timeout 15 manim gpu_test.py GPUTest -ql --renderer=opengl --disable_caching &
RENDER_PID=$!

# Monitor GPU usage during render
for i in {1..10}; do
    sleep 1
    echo "--- Second $i ---"
    rocm-smi --showuse --csv | grep "GPU use"
done

wait $RENDER_PID
echo "Render complete!"

echo "Test 2: Forcing RX 7700/7800 XT (GPU 1)" 
export MESA_VK_DEVICE_SELECT=1
export DRI_PRIME=1

echo "Starting second render test..."
timeout 15 manim gpu_test.py GPUTest3D -ql --renderer=opengl --disable_caching &
RENDER_PID=$!

# Monitor GPU usage during second render
for i in {1..10}; do
    sleep 1
    echo "--- GPU 1 Test Second $i ---"
    rocm-smi --showuse --csv | grep "GPU use"
done

wait $RENDER_PID
echo "All tests complete!"

echo "Final GPU status:"
rocm-smi --showuse --showmemuse
