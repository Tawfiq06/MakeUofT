import board
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306

WIDTH = 128
# 0.91" SSD1306 modules are often 128x32. Change to 64 if yours is 128x64.
HEIGHT = 32
MARGIN = 6

OLED_ADDR = 0x3C
_oled = None

printArtist = True

def _get_oled():
    """Lazy init so importing this module never disables the OLED forever."""
    global _oled
    if _oled is not None:
        return _oled

    # Initialize I2C and display
    i2c = busio.I2C(board.SCL, board.SDA)
    _oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=OLED_ADDR)

    # Clear display
    _oled.fill(0)
    _oled.show()
    return _oled

# Fonts
title_font = ImageFont.truetype(
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11
)
artist_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9
)

def clear():
    oled = _get_oled()
    oled.fill(0)
    oled.show()

def _centre_text(draw, text, y, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (WIDTH - w) // 2
    draw.text((x, y), text, font=font, fill=255)
    return h

def _wrap_text(draw, text, font, max_width):
    lines = []
    words = text.split()
    current_line = ""

    for word in words:
        test_line = current_line + " " + word if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines

def display_song(title, artist):
    oled = _get_oled()
    image = Image.new("1", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)

    #Wrap title
    max_width = WIDTH - (MARGIN * 2)
    title_lines =  _wrap_text(draw, title, title_font, max_width)

    #Limit title to max 2 lines
    title_lines = title_lines[:2]

    current_y = 3

    for line in title_lines:
        height = _centre_text(draw, line, current_y, title_font)
        current_y += height + 2 # spacing between lines

    current_y += 4

    #artist goes near bottom
    artist_height = draw.textbbox((0, 0), artist, font=artist_font)[3]
    artist_y = HEIGHT - artist_height - 3
    _centre_text(draw, artist, artist_y, artist_font)

    oled.image(image)
    oled.show()

    # Console output (match the display formatting)
    max_width = WIDTH - (MARGIN * 2)
    title_lines = _wrap_text(draw, title, artist_font, max_width)[:2]

    if title_lines:
        # Join multi-line titles with " / " to reflect wrapping
        print(f"Title: {' / '.join(title_lines)}")
        printArtist = False
    else:
        print("Title: ")
    print(" ")
    if printArtist:
        print(f"Artist: {artist}")