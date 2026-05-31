import re

with open("self_heal.py", "r") as f:
    text = f.read()

text = text.replace(
    '  (NOT a quoted string). Example: {"title":"My Title"} not "{\\"title\\":\\"My Title\\"}"".\\n\'',
    '  (NOT a quoted string). Example: {{"title":"My Title"}} not "{{\\"title\\":\\"My Title\\"}}".\\n\''
)

with open("self_heal.py", "w") as f:
    f.write(text)

