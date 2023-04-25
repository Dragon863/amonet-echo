import struct
import traceback

from amonet.common import Device
from amonet.handshake import handshake
from amonet.load_payload import load_payload
from amonet.logger import log

def switch_boot0(dev):
    dev.emmc_switch(1)
    block = dev.emmc_read(0)
    if block[0:9] != b"EMMC_BOOT" and block[0:9] != b"BADD_BOOT":
        #dev.reboot()
        print("what's wrong with your BOOT0?")

def flash_data(dev, data, start_block, max_size=0):
    while len(data) % 0x200 != 0:
        data += b"\x00"

    if max_size and len(data) > max_size:
        raise RuntimeError("data too big to flash")

    blocks = len(data) // 0x200
    for x in range(blocks):
        print("[{} / {}]".format(x + 1, blocks), end='\r')
        dev.emmc_write(start_block + x, data[x * 0x200:(x + 1) * 0x200])
    print("")

def read_boot0(dev):
    switch_boot0(dev)
    i = 0
    with open('boot0.bin', 'wb') as fout:
        while True:
            data = dev.emmc_read(i)
            fout.write(data)
            i = i + 1
    
#  read data. note: number of bytes is increased to nearest blocksize
def dump_binary(dev, outfile, start_block, nblocks=0):
    initialBlocks = nblocks
    with open(outfile, "wb") as fout:
        while nblocks > 0:
            data = dev.emmc_read(start_block)
            fout.write(data)
            start_block = start_block + 1
            nblocks = nblocks - 1
            print(str(100-((nblocks/initialBlocks)*100))+"%", end='\r')
            #print("[{} / {}]".format(nblocks, initialBlocks), end='\r')

    
def flash_binary(dev, path, start_block, max_size=0):
    with open(path, "rb") as fin:
        data = fin.read()
    while len(data) % 0x200 != 0:
        data += b"\x00"

    print(len(data))
    print(max_size)
    if max_size and len(data) > max_size:
        raise RuntimeError("data too big to flash")

    blocks = len(data) // 0x200
    for x in range(blocks):
        print("[{} / {}]".format(x + 1, blocks), end='\r')
        dev.emmc_write(start_block + x, data[x * 0x200:(x + 1) * 0x200])
    print("")

def switch_user(dev):
    dev.emmc_switch(0)
    block = dev.emmc_read(0)
    if block[510:512] != b"\x55\xAA":
        print(block[510:512])
        #dev.reboot()
        print("There may be a problem with your GPT. It is probably safe to ignore this.")

def parse_gpt(dev):
    data = dev.emmc_read(0x400 // 0x200) + dev.emmc_read(0x600 // 0x200) + dev.emmc_read(0x800 // 0x200) + dev.emmc_read(0xA00 // 0x200)
    num = len(data) // 0x80
    parts = dict()
    for x in range(num):
        part = data[x * 0x80:(x + 1) * 0x80]
        part_name = part[0x38:].decode("utf-16le").rstrip("\x00")
        part_start = struct.unpack("<Q", part[0x20:0x28])[0]
        part_end = struct.unpack("<Q", part[0x28:0x30])[0]
        parts[part_name] = (part_start, part_end - part_start + 1)
        pass
    return parts

def main():
    print("Please short the emmc as instructed in the article or readme.")
    while True:
        try:
            dev = Device()
            dev.find_device()

            # 0.1) Handshake
            handshake(dev)
        except RuntimeError:
            log("wrong handshake response, probably in preloader")
            continue
        log("handshake success!")
        break

    # 0.2) Load brom payload
    load_payload(dev, "brom-payload/build/payload.bin")

    # 1) Sanity check GPT
    log("Check GPT")
    switch_user(dev)

    # 1.1) Parse gpt
    gpt = parse_gpt(dev)
    print("Partitions:")
    print(gpt)
    print()
    if "lk_a" not in gpt or "tee1" not in gpt or "boot_a" not in gpt or "misc" not in gpt:
        print("There may be an issue with your GPT. If the partitions shown above have readable names, it is safe to continue. Press enter to proceed...")
        input()
    
    print("Do you want to dump the userdata partition (with wifi information in) or system partition?")
    part = input("[1 = system, 2 = userdata, 3 = custom partition] >> ")
    if part == '1':
        print("Warning: this process can take a LONG time. I recommend leaving this running overnight. Press enter to proceed...")
        input()
        print("Writing contents of system_a to system.img...")
        dump_binary(dev, "system.img", gpt["system_a"][0], gpt["system_a"][1])
    elif part == '2':
        print("Warning: this process can take a LONG time. I recommend leaving this running overnight. Press enter to proceed...")
        input()
        print("Writing contents of userdata to userdata.img...")
        dump_binary(dev, "userdata.img", gpt["userdata"][0], gpt["userdata"][1])
    elif part == '3':
        print("Which partition do you want to dump?")
        part = input(">> ")
        print("Warning: this process can take a LONG time. I recommend leaving this running overnight. Press enter to proceed...")
        input()
        print(f"Writing contents of {part} to {part}.img...")
        try:
            dump_binary(dev, f"{part}.img", gpt[part][0], gpt[part][1])
            print("Partition dump complete!")
        except Exception as e:
            print("Sorry, an error occurred dumping that partition. Please check that its name is spelt correctly. Press enter to view error...")
            input()
            traceback.print_exc()

    exit("Execution ended.")


if __name__ == "__main__":
    main()
