import board
import busio
from PIL import Image, ImageDraw, ImageFont
import adafruit_ssd1306
from recognize import recognize

WIDTH = 128
HEIGHT = 64
MARGIN = 6

# Initailze I2C and display
i2c = busio.I2C(board.SCL, board.SDA)
oled = adafruit_ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c)

# Clear display on startup

oled.fill(0)
oled.show()

# Fonts
title_font = ImageFont.truetype(
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14
)
artist_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10
)

def clear():
    oled.fill(0)
    oled.show()

def _centre_text(draw, text, y, font):
    w, h = draw.textsize(text, font=font)
    x = (WIDTH - w) // 2
    draw.text((x,y), text, font=font, fill=255)
    return h

def _wrap_text(draw, text, font, max_width):
    lines = []
    words = text.split()
    current_line = ""

    for word in words:
        test_line = current_line + " " + word if current_line else word
        w, _ = draw.textsize(test_line, font=font)
        if w <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines

def display_song(title, artist):
    image = Image.new("1", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(image)

    #Wrap title
    max_width = WIDTH - (MARGIN * 2)
    title_lines =  _wrap_text(draw, title, title_font, max_width)

    #Limit title to max 2 lines
    title_lines = title_lines[:2]

    current_y = 8

    for line in title_lines:
        height = _centre_text(draw, line, current_y, title_font)
        current_y += height + 2 # spacing between lines

    current_y += 4

    #artist goes near bottom
    artist_height = draw.textbbox((0, 0), artist, font=artist_font)[3]
    artist_y = HEIGHT - artist_height - 10
    _centre_text(draw, artist, artist_y, artist_font)

    oled.image(image)
    oled.show
    
    print("OLED ok")