import time
from config import DEBUG


def timeit(foo):
    def timer(*arg, **kwargs):
        if DEBUG:
            start = time.time()
            res = foo(*arg, **kwargs)
            print('timeit : ', end='')
            print(foo.__name__ + ' : ', end='')
            print(time.time() - start, end='')
            print(' seconds.')
            return res
        else:
            return foo(*arg, **kwargs)
    return timer
