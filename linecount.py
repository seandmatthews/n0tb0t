from os import listdir
from os.path import isfile, join


def count_lines_in_path(path, directory):
    count = 0
    for _ in open(join(directory, path), encoding="utf8"):
        count += 1
    return count


def count_lines(paths, directory):
    count = 0
    for path in paths:
        count = count + count_lines_in_path(path, directory)
    return count


def get_paths(directory):
    return [f for f in listdir(directory) if isfile(join(directory, f))]


def count_line(directory):
    return count_lines(get_paths(directory), directory)


if __name__ == '__main__':
    lines = 0
    lines += count_line('.')
    lines += count_line(r'src')
    lines += count_line(r'src\modules')
    lines += count_line(r'tests\unit_tests')
    print(lines)

