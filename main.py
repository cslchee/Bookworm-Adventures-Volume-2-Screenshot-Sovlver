from PIL import Image
import easyocr
import numpy as np
from collections import Counter
import json, time, os
from dotenv import load_dotenv
from math import sqrt
import tile_palettes

load_dotenv()

"""
Finds the best possible words for a set of tiles in Bookworm Adventures Volume 2 based on a screenshot
Requires:
    -   Download required libraries (EasyOCR is pretty big)
    -   An '.env' file with the key 'USER_ID' to your directory
        (Or just copy your directory into the 'screenshot_dir' constant and delete the 'dot_env' stuff)
Notes:
    - Does not take into account the color of gemstones when calculating/sorting by damage.
    - Bookwork Adventures Vol. 2 is no longer available for purchase on Steam.
    - Easy OCR is better than Pytesserect (even with "--psm 11"), but it's still not perfect.

Potential Improvements:
    - Only show the top 10 results for each tier of letter count to avoid clutter.

"""

# Constants
USER_ID = os.getenv('USER_ID')
SCREENSHOT_DIR = f"C:\\Program Files (x86)\\Steam\\userdata\\{USER_ID}\\760\\remote\\3630\\screenshots"
WAIT_TIME = 5 #seconds, keeps the while loop occupied

# Globals
analyzed_images = [] #For remember
reader = easyocr.Reader(["en"], gpu=True)


def clear_screenshots_folder() -> None:
    print("Deleting existing screenshots!")
    for file in os.listdir(SCREENSHOT_DIR):
        file_path = os.path.join(SCREENSHOT_DIR, file)
        if os.path.isfile(file_path):
            os.remove(file_path)
    print("Done!")

def get_board_letters() -> str:
    #Get the newest screenshot
    files = [f for f in os.listdir(SCREENSHOT_DIR) if os.path.isfile(os.path.join(SCREENSHOT_DIR, f))] # get all files from the directory
    if not len(files): # len() == 0
        return "" # No files found
    else:
        newest_file = files[-1]

    if newest_file not in analyzed_images:
        print(f"Newest file: {newest_file}")
        image = Image.open(f"{SCREENSHOT_DIR}\\{newest_file}")

        cropped_image = image.crop((302, 310, 502, 510)) #Only get the letters on the board, 200x200

        # Get a cropped Image of each letter
        individual_letters = []
        for y in range(4):
            for x in range(4):
                x_cor = x * 50
                y_cor = y * 50
                individual_letters.append(cropped_image.crop((x_cor, y_cor, x_cor+50, y_cor+50)))

        # Function to calculate the Euclidean distance between two RGB values
        def color_distance(color1, color2):
            return sqrt(sum((c1 - c2) ** 2 for c1, c2 in zip(color1, color2)))

        # Function to calculate the distance between two palettes
        def palette_distance(palette1, palette2):
            # Calculate the sum of minimum distances from each color in palette1 to palette2
            return sum(min(color_distance(color1, color2) for color2 in palette2) for color1 in palette1)

        # Function to find the closest palette to an image's palette
        def find_closest_palette(tile_image: Image, existing_palettes, num_colors=8):
            # Open the image and reduce it to its primary colors
            colors = tile_image.getcolors(tile_image.size[0] * tile_image.size[1])  # Get all colors
            colors = sorted(colors, key=lambda x: x[0], reverse=True)  # Sort by frequency
            tile_palette = [color[1] for color in colors[:num_colors]]  # Take the top N colors

            # Find the closest existing palette
            closest_palette = min(existing_palettes, key=lambda palette: palette_distance(tile_palette, palette))
            return closest_palette

        gems = []
        for letter in individual_letters:
            letter_closest_palette = find_closest_palette(letter, tile_palettes.raw_palettes, num_colors=8)
            letter_gem = [key for key, value in tile_palettes.tile_palettes.items() if value['palette'] == letter_closest_palette]
            gems.append(letter_gem)
        print(gems)
        # TODO Compare tile to closest jem, get dictionary of multipliers & associate letters


        # Cconvert to greyscale
        cropped_image = cropped_image.convert("L")

        # Using cropped pillow image and EasyOCR
        np_image = np.array(cropped_image)

        raw_text = reader.readtext(np_image, detail=0) # Get text, ignore numeric details
        text = ''.join(raw_text).lower().strip()

        # Process text to clear out obvious inaccuracies
        for x, y in ((' ',''),('|',''),('0','o')): # Common bonus symbols
            text = text.replace(x, y)
        for x in range(1,10): #In case it catches tile countdowns
            text = text.replace(str(x),'')

        analyzed_images.append(newest_file) # Add to the list of known files

        return text
    else:
        return ""

def word_damage_calculator(word: str) -> int:
    DAMAGE_AMOUNTS = {  # Taken From https://www.speedrun.com/bookworm_adventures_volume_2/guides/6x3x1
        1: "adegilnorstu",
        1.25: 'bcfhmp',
        1.5: 'vwy',
        1.75: 'jk',
        2: 'xz'
    }
    damage = 0

    # Two-letter tile exception
    if 'qu' in word:
        damage += 2.75
        word = word.replace('qu', '')
        print(f"\tFound a 'qu' word: {word}") # Debugging the two-letter tile 'qu' situation

    #Scan letters, add up their damage
    for letter in word:
        for key, value in DAMAGE_AMOUNTS.items():
            if letter in value:
                damage += key
    #print(f"{word} --> {damage}")
    return round(damage, 2) # Remove all the ".0" for whole numbers


def main():
    input("Greetings.\nPress enter to delete current Bookworm Adventures Vol. 2 Screenshots and then begin! >_")
    clear_screenshots_folder()
    print(f"Current wait time between folder checks is {WAIT_TIME} seconds.\nPress F12 to take Steam screenshots.")

    # Get all the words
    with open('./ba2_words.json', 'r') as file:
        full_word_set = json.load(file)['words']

    # Filter out words larger than 16 (max possible letters [only one in new local database]) and above 4 (ignore the simple stuff)
    ALL_WORDS = tuple([word for word in full_word_set if 16 >= len(word) > 5])

    # Periodically scan the directory for new images, then test new ones for the best possible combinations
    while True:
        input_letters = get_board_letters()
        if input_letters:
            print(f'For Letters: "{input_letters}"')
            letter_count = Counter(input_letters)

            # Sort which ones are valid
            valid_words = []
            for word in ALL_WORDS:
                word_counter = Counter(word)
                if all(letter_count[char] >= word_counter[char] for char in word): # Word has all the right characters
                    # Avoids the 'u' in the 'qu' tile being used freely
                    # TODO Might exclude 'u' if there's another 'u' outside of the 'qu' in the set
                    if 'qu' in input_letters and 'u' in word and 'qu' not in word:
                        continue # Skip word if it's using the 'u' that belongs to the 'qu' out of place

                    valid_words.append(word)

            # Sort them by the amount of damage the words do, then print the results
            valid_words.sort(key=word_damage_calculator, reverse=True)
            for index, word in enumerate(valid_words[:50], start=1):
                print(f"{word:16}->[{word_damage_calculator(word):4}]  ", end="\n" if index % 5 == 0 else "")
            print(f"\n{'- ' * 30}")

        time.sleep(WAIT_TIME)


if __name__ == '__main__':
    main()
