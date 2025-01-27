import sys
LIMIT = 1 << 12

if len(sys.argv) != 2:
    print(f"Usage: {sys.argv[0]} <in>")

infile = sys.argv[1]
with open(infile, 'r') as f:
    lines = f.readlines()

encodings = {
    "dat": 0,
    "mov": 1,
    "add": 2,
    "sub": 3,
    "jmp": 4,
    "jmz": 5,
    "djz": 6,
    "cmp": 7
}

special = ["dat", "jmp"]

def parse_arg(a):
    mode = 1

    integer = a

    if a[0] in "#@":
        if a[0] == "#":
            mode = 0
        if a[0] == "@":
            mode = 2
        integer = a[1:]
    i = int(integer)
    if not (-LIMIT < i < LIMIT):
        raise ValueError("Number too large")
    while (i < 0):
        i += LIMIT
    return mode, i

line = 1
ip = 0

load_at = 0

assembly = []
for l in lines:
    l = l.strip()
    # ignore comments and blanks
    if ((len(l) == 0) or (l[0] == ';')):
        continue

    tokens = l.split()
    operation = tokens[0]
    if operation not in encodings:
        if operation == "LOAD":
            load_at = ip
            continue
        else:
            raise ValueError(f"Error on line {line}, unknown opcode {operation}")

    ins = 0
    ins |= encodings[operation] << 28

    if operation in special:
        mode_b, b = parse_arg(tokens[1])
        ins |= mode_b << 24
        ins |= b
    else:
        mode_a, a = parse_arg(tokens[1])
        mode_b, b = parse_arg(tokens[2])
        ins |= mode_a << 26
        ins |= a << 12
        ins |= mode_b << 24
        ins |= b
    assembly.append(ins)
    ip += 1

assembly = [load_at] + assembly
out = ", ".join([hex(x) for x in assembly])
print(f"[{out}]")

