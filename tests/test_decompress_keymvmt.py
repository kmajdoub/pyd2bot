compressed = 28802
orientation = compressed >> 12 
cellId =  compressed & 4095
print(orientation, cellId)

compressed2 = orientation << 12 + cellId & 4095

assert compressed == compressed