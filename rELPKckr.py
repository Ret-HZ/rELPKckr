# MIT License

# Copyright (c) 2021 Christopher Holzmann Pérez

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.



from binary_reader import BinaryReader
import argparse
import gzip
import json
import sys
import os



__version__ = "1.4.0"

METADATA_FILENAME = "_metadata.json"
METADATA_WARNING = "This file has been generated by rELPKckr and is necessary to rebuild the archive correctly. Please do not edit it if you don't know what you are doing."
METADATA_USAGE = "ELPK contents will be written in the same order as they appear in the following list. Should any additional files be present in the unpacked directory, they will be added at the end in alphabetical order. Hashes are only for reference and will not be used during the repacking process."

FILENAME_DICT = dict()


def rchop(s, suffix):
    if suffix and s.endswith(suffix):
        return s[:-len(suffix)]
    return s


# Thanks to SutandoTsukai181
# https://github.com/SutandoTsukai181/kurohyo_lib/blob/c8e7bff39b9cecacdbc6b453b0774a7cb0b3b7d3/kurohyo_lib/structure/common.py#L6
def hash_fnv0(string):
    max_size = 2**32
    prime = 0x811C9DC5

    result = 0
    for c in string:
        result = (result * prime) % max_size
        result ^= ord(c)

    return result


def hash_to_str(val: int):
    return val.to_bytes(4, byteorder='little').hex().upper()


def hash_to_int(val: str):
    return int.from_bytes(bytes.fromhex(val), byteorder='little')


def open_filename_list():
    filepath = os.path.join(os.path.dirname(__file__), "filenames.txt")

    if not os.path.exists(filepath):
        return

    with open(filepath, "r") as file:
        global FILENAME_DICT
        filename_list = file.readlines()
        filename_list[:] = [s.strip() for s in filename_list]

        FILENAME_DICT = {
            hash_fnv0(s): s
            for s in filename_list
        }


def get_name_from_hash(hash: int) -> str:
    global FILENAME_DICT
    # Return file name if available, else hash bytes in little endian hexadecimal
    return FILENAME_DICT.get(hash, hash_to_str(hash))


def extractELPK (path, extension_hash: bool):
    f = open(path, "rb")

    reader = BinaryReader(f.read())

    is_compressed = False
    if reader.read_bytes(2) == b'\x1f\x8b':
        # Decompress gzip
        reader = BinaryReader(gzip.decompress(reader.buffer()))
        is_compressed = True

    reader.seek(0)

    if reader.read_str(4) != 'ELPK':
        raise Exception('Incorrect magic. Expected ELPK')

    metadata = dict()
    metadata["Warning"] = METADATA_WARNING
    metadata["Usage"] = METADATA_USAGE
    metadata["Compressed"] = is_compressed
    metadata["Files"] = dict()

    open_filename_list()

    elpk_size = reader.read_uint32()
    unknown = reader.read_uint32()
    padding = reader.read_uint32()
    file_number = reader.read_uint32()

    for i in range(file_number):
        file_name_hash = reader.read_uint32() #File name hash. Will be used as the actual file name if no matching names are found.
        file_name = get_name_from_hash(file_name_hash)
        print("Extracting", file_name)
        file_ptr = reader.read_uint32()
        file_size = reader.read_uint32()

        pos = reader.pos()
        reader.seek(file_ptr)

        file_data = reader.read_bytes(file_size)
        
        #Since there are no file extensions, try to use the magic as file extension
        readertemp = BinaryReader(file_data)
        try: #Yes, this is a terrible way of doing this
            try:
                newfile_magic = readertemp.read_str(4)
                if (len(newfile_magic) == 4):
                    magic_is_bad = any(not c.isalnum() for c in newfile_magic)
                    if magic_is_bad:
                        raise Exception("bad 4 char magic")
                else:
                    raise Exception("magic length less than 4")
            except:
                readertemp.seek(0)
                newfile_magic = readertemp.read_str(3)
                if (len(newfile_magic) == 3):
                    magic_is_bad = any(not c.isalnum() for c in newfile_magic)
                    if magic_is_bad:
                        raise Exception("bad 3 char magic")
                else:
                    raise Exception("magic length less than 3")
        except:
            newfile_magic = "dat" #Default extension
        newfile_magic = newfile_magic.lower()

        folder_name = path + ".unpack"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        file_meta = dict()
        file_meta["HashIsName"] = True if hash_to_str(file_name_hash) == file_name else False

        if extension_hash and not file_meta["HashIsName"]:
            file_name = f'{file_name}._{hash_to_str(file_name_hash)}'

        file_meta["Hash"] = file_name_hash
        metadata["Files"][f"{file_name}.{newfile_magic}"] = file_meta

        extracted_file_path = f"{folder_name}/{str(file_name)}.{newfile_magic}"
        print("Saving", extracted_file_path)
        with open(extracted_file_path, 'wb') as file:
            file.write(file_data)
            file.close()

        reader.seek(pos)

    #Save metadata
    with open(f"{folder_name}/{METADATA_FILENAME}", "w") as metafile:
        json.dump(metadata, metafile, indent=2)


def writeELPKContent (writer: BinaryReader, main_table_pos: int, path: str, filename: str, hash_is_name: bool):
    print(f"Packing {filename}")
    filename_no_ext = filename.split(".")[0]
    file_path = (f"{path}/{filename}").encode("utf8")
    if not os.path.isfile(file_path): #Abort if files are missing
        raise Exception(f"{filename} not found.")
    data_ptr = writer.pos()
    file = open(file_path, "rb")
    file_bytearray = bytearray(file.read())
    writer.write_bytes(bytes(file_bytearray))
    file_data_pos = writer.pos()

    writer.seek(main_table_pos) #Go back to the main table and update the corresponding data
    if hash_is_name:
        writer.write_uint32(hash_to_int(filename_no_ext))
    else:
        writer.write_uint32(int(hash_fnv0(filename_no_ext)))
    writer.write_uint32(data_ptr)
    writer.write_uint32(len(file_bytearray))
    main_table_pos = writer.pos()

    writer.seek(file_data_pos) #Back to the data section for the next iteration
    return main_table_pos


def repackELPK (path):
    new_path = rchop(path, ".unpack")
    if os.path.isfile(new_path):
        choice = input("WARNING: Output file already exists. It will be overwritten.\nContinue? (y/n) ")
        if not choice.lower() == "" and not choice.lower().startswith('y'):
            print("ELPK repacking cancelled.")
            sys.exit(2)

    metafile = open(f"{path}/{METADATA_FILENAME}", "r")
    metadata = json.load(metafile)
    metafile.close()

    writer = BinaryReader()
    writer.write_str('ELPK')
    writer.write_uint32(0) #File size placeholder
    writer.write_uint32(152048384) #Unknown. Always the same
    writer.write_uint32(0)

    #General directory file list
    dir_list = os.listdir(path)
    file_list = []
    for name in dir_list:
        if os.path.isfile(f"{path}/{name}"):
            file_list.append(name)
    file_list.remove(METADATA_FILENAME)

    file_list_in_meta = list(metadata["Files"].keys()) #Files in the metafile. Will have priority over non indexed files.

    writer.write_uint32(len(file_list)) #File amount
    print(f"Found {len(file_list)} files.")

    main_table_pos = writer.pos() #Pointer to the main table
    file_data_pos = writer.pos() #Pointer to the file data section

    file_list = sorted(file_list)
    for filename in file_list:
        writer.write_uint32(0) #Placeholder file name hash
        writer.write_uint32(0) #Placeholder pointer to data
        writer.write_uint32(0) #Placeholder file size
    writer.align(0x10)

    #Write files listed in metadata first, then other files found in the directory
    for filename in file_list_in_meta:
        try:
            main_table_pos = writeELPKContent(writer, main_table_pos, path, filename, metadata["Files"][filename]["HashIsName"])
            file_list.remove(filename)
        except: #The file is listed in the metadata file but isn't present in the directory
            print(f"{filename} was missing or could not be written. Skipping...")

    for filename in file_list:
        main_table_pos = writeELPKContent(writer, main_table_pos, path, filename, False)

    writer.align(0x10)
    writer.seek(0x4)
    writer.write_uint32(writer.size())

    #Compress if needed
    if metadata["Compressed"]:
        bytes_to_write = gzip.compress(writer.buffer(), compresslevel=6, mtime=0)
    else:
        bytes_to_write = writer.buffer()

    #Write ELPK
    with open(new_path, 'wb') as file:
        file.write(bytes_to_write)
        file.close()



if __name__ == '__main__':
    print(r'''
      _____ _    ______ _   __     _         
     |  ___| |   | ___ \ | / /    | |        
 _ __| |__ | |   | |_/ / |/ /  ___| | ___ __ 
| '__|  __|| |   |  __/|    \ / __| |/ / '__|
| |  | |___| |___| |   | |\  \ (__|   <| |   
|_|  \____/\_____|_|   \_| \_/\___|_|\_\_|                                      
    ''')
    print(f"Version: {__version__}\n")
    parser = argparse.ArgumentParser()
    parser.add_argument("input",  help='Input file (ELPK) or directory to pack', type=str)
    parser.add_argument('-ext', '--extension-hash', action='store_true', help='Add hash (hex little endian) before file extension when unpacking, if the filename is available (does not affect repacking)')
    if len(sys.argv) < 2:
        parser.print_help()
        input("\nPress ENTER to exit...")
        sys.exit(1)
    args = parser.parse_args()

    path = args.input

    if os.path.isfile(path):
        extractELPK(path, args.extension_hash)
    if os.path.isdir(path):
        repackELPK(path)