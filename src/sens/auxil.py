def rescale(x, min, max):
    return min + x * (max - min)

def rescale_mean(x, mean, percent):
    min = mean * (100.0 - percent)/100.0
    max = mean * (100.0 + percent)/100.0
    return rescale(x, min, max)

class Subslicer:
    def __init__(self, array):
        self.array = array
        self.i = -1
        self.n = self.array.shape[0]
    def get(self):
        self.i +=1
        if self.i < self.n:
            return self.array[self.i]
        else:
            print("Array out of bounds")
            exit(99)
            return None