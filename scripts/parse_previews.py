import os

def parse_previews(input_file, output_file):
    images = {}
    current_image = None
    current_data = []
    
    with open(input_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('PREVIEW_START:'):
                current_image = line.split(':', 1)[1]
                current_data = []
            elif line.startswith('PREVIEW_END:'):
                if current_image:
                    images[current_image] = ''.join(current_data)
                    current_image = None
            elif current_image:
                current_data.append(line)

    with open(output_file, 'w') as f:
        f.write('// Auto-generated demo images\n')
        for path, data in images.items():
            if 'lucchiIm.tif' in path:
                f.write(f"export const DEMO_IMAGE_PREVIEW = '{data}'\n")
            elif 'lucchiLabels.tif' in path:
                f.write(f"export const DEMO_LABEL_PREVIEW = '{data}'\n")

if __name__ == "__main__":
    input_path = '/Users/adamg/seg.bio/pytc-client/scripts/preview_output.txt'
    output_path = '/Users/adamg/seg.bio/pytc-client/client/src/utils/demo_images.js'
    parse_previews(input_path, output_path)
    print(f"Generated {output_path}")
