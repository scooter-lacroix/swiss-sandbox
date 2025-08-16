#!/usr/bin/env python3

import matplotlib.pyplot as plt
from PIL import Image
import os

def display_screenshots():
    # Get all the key screenshots
    screenshots = [
        ("/home/stan/Pictures/Screenshots/Screenshot from showcase_ultimate_mandelbrot_fixed.mp4 - 1.png", "Mandelbrot 1"),
        ("/home/stan/Pictures/Screenshots/Screenshot from showcase_ultimate_mandelbrot_fixed.mp4 - 2.png", "Mandelbrot 2"),
        ("/home/stan/Pictures/Screenshots/Screenshot from SwissSandboxJuliaUltimate.mp4 - 1.png", "Julia 1"),
        ("/home/stan/Pictures/Screenshots/Screenshot from SwissSandboxJuliaUltimate.mp4 - 2.png", "Julia 2"),
        ("/home/stan/Pictures/Screenshots/Screenshot from SwissSandboxKochUltimate.mp4 - 1.png", "Koch 1"),
        ("/home/stan/Pictures/Screenshots/Screenshot from SwissSandboxKochUltimate.mp4 - 2.png", "Koch 2")
    ]
    
    # Set up the plot
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('Swiss Sandbox Animation Screenshots Analysis', fontsize=16)
    
    for i, (screenshot_path, title) in enumerate(screenshots):
        row = i // 3
        col = i % 3
        ax = axes[row, col]
        
        if os.path.exists(screenshot_path):
            img = Image.open(screenshot_path)
            ax.imshow(img)
            ax.set_title(title)
            ax.axis('off')
        else:
            ax.text(0.5, 0.5, f'File not found:\n{title}', 
                   ha='center', va='center', transform=ax.transAxes)
            ax.axis('off')
    
    plt.tight_layout()
    plt.savefig('screenshot_analysis.png', dpi=150, bbox_inches='tight')
    print("Screenshots saved to 'screenshot_analysis.png'")
    plt.show()

if __name__ == "__main__":
    display_screenshots()
