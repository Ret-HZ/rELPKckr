from binary_reader import BinaryReader
import argparse
import os
import gzip



def rchop(s, suffix):
    if suffix and s.endswith(suffix):
        return s[:-len(suffix)]
    return s



def extractELPK (path):
    f = open(path, "rb")

    reader = BinaryReader(f.read())

    if reader.read_bytes(2) == b'\x1f\x8b':
        # Decompress gzip
        reader = BinaryReader(gzip.decompress(reader.buffer()))

    reader.seek(0)

    if reader.read_str(4) != 'ELPK':
        raise Exception('Incorrect magic. Expected ELPK')

    elpk_size = reader.read_uint32()
    unknown = reader.read_uint32()
    padding = reader.read_uint32()
    file_number = reader.read_uint32()

    for i in range(file_number):
        file_name_numeric = reader.read_uint32() #File name hash? Will be used as the actual file name
        print("Extracting", str(file_name_numeric))
        filePtr = reader.read_uint32()
        fileSize = reader.read_uint32()

        pos = reader.pos()
        reader.seek(filePtr)

        fileData = reader.read_bytes(fileSize)
        
        #Since there are no file extensions, try to use the magic as file extension
        readertemp = BinaryReader(fileData)
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

        folder_name = path + ".unpack"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        extracted_file_path = folder_name + "/" + str(i+1).rjust(5, '0') + "-" + str(file_name_numeric) + "." + newfile_magic.lower()
        print("Saving", extracted_file_path)
        with open(extracted_file_path, 'wb') as file:
            file.write(fileData)
            file.close()

        reader.seek(pos)



def repackELPK (path):
    writer = BinaryReader()
    writer.write_str('ELPK')
    writer.write_uint32(0) #File size placeholder
    writer.write_uint32(152048384) #I have no clue what this is
    writer.write_uint32(0)

    dir_list = os.listdir(path)
    file_list = []
    for name in dir_list:
        if os.path.isfile(path + "/" + name):
            file_list.append(name)

    writer.write_uint32(len(file_list)) #File amount
    print("Detected", str(len(file_list)), "files")

    main_table_pos = writer.pos() #Pointer to the main table
    file_data_pos = writer.pos() #Pointer to the file data section

    file_list = sorted(file_list)
    for filename in file_list:
        writer.write_uint32(0) #Placeholder name or whatever this is
        writer.write_uint32(0) #Placeholder pointer to data
        writer.write_uint32(0) #Placeholder file size
    writer.align(0x10)

    for filename in file_list:
        print("Packing", filename)
        file_path = (path + "/" + filename).encode("utf8")
        data_ptr = writer.pos()
        file = open(file_path, "rb")
        file_bytearray = bytearray(file.read())
        writer.write_bytes(bytes(file_bytearray))
        file_data_pos = writer.pos()

        writer.seek(main_table_pos) #Go back to the main table and update the corresponding data
        writer.write_uint32(int(filename.split(".")[0].split("-")[1]))
        writer.write_uint32(data_ptr)
        writer.write_uint32(len(file_bytearray))
        main_table_pos = writer.pos()

        writer.seek(file_data_pos) #Back to the data section for the next iteration
         
    writer.align(0x10)
    writer.seek(0x4)
    writer.write_uint32(writer.size())

    new_path = rchop(path, ".unpack")
    with open(new_path, 'wb') as file:
        file.write(writer.buffer())
        file.close()



if __name__ == '__main__':
    print("rELPKckr by Capitán Retraso \n")
    parser = argparse.ArgumentParser()
    parser.add_argument("input",  help='Input file (ELPK) or directory to pack', type=str)
    args = parser.parse_args()

    path = args.input

    if os.path.isfile(path):
        extractELPK(path)
    if os.path.isdir(path):
        repackELPK(path)