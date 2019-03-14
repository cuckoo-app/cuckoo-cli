import sys
import time

if __name__ == '__main__':
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    else:
        n = 5
    for i in range(n):
        print(i)
        time.sleep(1)
    # raise Exception('oh')
