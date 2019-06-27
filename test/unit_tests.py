#! /usr/bin/python

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../libigcc"))

import re

import libigcc.run
import libigcc.source_code
from libigcc.run import UserInput

import inspect


class FakeWriteableFile:
    def __init__(self):
        self.lines = []

    def write(self, line):
        self.lines.append(line)


class FakeReadableFile:
    def __init__(self, lines):
        self.lines = lines

    def readline(self):
        if len(self.lines) == 0:
            return None
        line = self.lines[0]
        self.lines = self.lines[1:]
        return line


def assert_strings_equal(str1, str2, strict=False):
    if (not strict and [c for c in str1 if c.isalpha()] == [c for c in str2 if c.isalpha()]) or \
            (strict and str1 == str2):
        return

    raise AssertionError("\n" + str1 + "\n!=\n" + str2)


def assert_strings_match(string, re_string):
    cmp_re = re.compile(re_string)

    if cmp_re.match(string):
        return

    raise AssertionError("\n[" + string + "]\ndoes not match regular expression\n[" + re_string + "]")


def run_program(commands, expected_output, argv=None):
    outputfile = FakeWriteableFile()
    stdin_file = FakeReadableFile(commands)
    ret = libigcc.run.run(outputfile, stdin_file, argv)

    assert_strings_equal("".join(outputfile.lines), expected_output)

    return ret


def run_program_regex_output(commands, expected_output_re):
    outputfile = FakeWriteableFile()
    stdin_file = FakeReadableFile(commands)
    libigcc.run.run(outputfile, stdin_file, argv=None)

    assert_strings_match("".join(outputfile.lines), expected_output_re)


def test_declare_var():
    commands = ["int a;"]
    expected_output = 'g++> int a;\ng++> \n'
    run_program(commands, expected_output)


def test_declare_var_assign():
    commands = ["int a;", "a = 10;"]
    expected_output = 'g++> int a;\ng++> a = 10;\ng++> \n'
    run_program(commands, expected_output)


def test_declare_and_assign_var_then_print():
    commands = ["int a = 10;",
                'printf( "%d\\n", a );']

    expected_output = (
        '''g++> int a = 10;
        g++> printf( "%d\\n", a );
        10
        g++>
        ''')

    run_program(commands, expected_output)


def test_print_twice():
    commands = ["int a = 10;",
                'printf( "%d\\n", a );',
                "++a;",
                'printf( "%d\\n", a );']

    expected_output = (
        '''g++> int a = 10;
        g++> printf( "%d\\n", a );
        10
        g++> ++a;
        g++> printf( "%d\\n", a );
        11
        g++>
        ''')

    run_program(commands, expected_output)


def test_compile_error():
    commands = ["int a"]  # no semicolon

    expected_output = (
        '''g++> int a
        [Compile error - type .e to see it.]
        g++>
        ''')

    run_program(commands, expected_output)


def test_compile_error_display():
    commands = [
        "int a",  # no semicolon
        ".e"]

    # Just look for a string "xpected" in the compiler output.
    expected_output_re = inspect.cleandoc(
        '''g\+\+\> int a
        \[Compile error - type \.e to see it\.\]
        g\+\+\> \.e
        (.(\s)*)*error:(.(\s)*)*
        g\+\+\> $''')

    run_program_regex_output(commands, expected_output_re)


def test_include():
    commands = [
        '#include <vector>',
        'std::vector<int> vec;',
        r'printf( "%d\n", vec.size() );']

    expected_output = (
        r'''g++> #include <vector>
        g++> std::vector<int> vec;
        g++> printf( "%d\n", vec.size() );
        0
        g++>
        ''')

    run_program(commands, expected_output)


def test_multiple_repeated_includes():
    commands = [
        '  #  include   <vector> ',
        'std::vector<int> vec;',
        '#include <iostream>',
        ' #   include   <vector>',
        '#include <iostream>',
        'using namespace std;',
        'cout << vec.size() << std::endl;']

    expected_output = (
        r'''g++>   #  include   <vector>
        g++> std::vector<int> vec;
        g++> #include <iostream>
        g++>  #   include   <vector>
        g++> #include <iostream>
        g++> using namespace std;
        g++> cout << vec.size() << std::endl;
        0
        g++>
        ''')

    run_program(commands, expected_output)


def test_list_program():
    commands = [
        'int a;',
        'a += 2;',
        '#include <vector>',
        '.l']

    expected_output = (
        r'''g++> int a;
        g++> a += 2;
        g++> #include <vector>
        g++> .l
        #include <vector>

        int a;
        a += 2;

        g++>
        ''')

    run_program(commands, expected_output)


class FakeRunner:
    def __init__(self, user_commands_string, user_includes_string):
        self.user_commands_string = user_commands_string
        self.user_includes_string = user_includes_string

    def get_user_commands_string(self):
        return self.user_commands_string

    def get_user_includes_string(self):
        return self.user_includes_string


def test_list_full_program():
    commands = [
        'int a;',
        'a += 2;',
        '#include <vector>',
        '.L']

    fakerunner = FakeRunner('int a;\na += 2;\n',
        "#include <vector>\n")

    expected_output = (
            '''g++> int a;
            g++> a += 2;
            g++> #include <vector>
            g++> .L
            %s
            g++>
            ''' % libigcc.source_code.get_full_source(fakerunner))

    run_program(commands, expected_output)


def test_help_message():
    commands = [
        '.h']

    expected_output_re = "(.(\s)*)*Show this help message(.(\s)*)*"

    run_program_regex_output(commands, expected_output_re)


def test_quit():
    commands = [
        '.q']

    expected_output = "g++> .q\n"

    ret = run_program(commands, expected_output)

    assert_strings_equal(ret, "quit")


def test_include_dir_on_cmd_line():
    commands = ['#include "hello.h"',
                'hello();']

    expected_output = (
        '''g++> #include "hello.h"
        g++> hello();
        Hello,
        g++>
        ''')

    argv = ["-I", "cpp"]

    run_program(commands, expected_output, argv=argv)


def test_2_include_dirs_on_cmd_line():
    commands = ['#include "hello.h"',
                'hello();',
                '#include "world.h"',
                'world();', ]

    expected_output = (
        '''g++> #include "hello.h"
        g++> hello();
        Hello,
        g++> #include "world.h"
        g++> world();
        world!
        g++>
        ''')

    argv = ["-I", "cpp", "-I", "cpp2"]

    run_program(commands, expected_output, argv=argv)


def test_lib():
    commands = ['#include "math.h"',
                'int a = max( 4, 6 );',
                r'printf( "%d\n", a );', ]

    expected_output = (
        r'''g++> #include "math.h"
        g++> int a = max( 4, 6 );
        g++> printf( "%d\n", a );
        6
        g++>
        ''')

    argv = ["-lm"]

    run_program(commands, expected_output, argv=argv)


def test_runner_get_user_input():
    runner = libigcc.run.Runner(None, None, None)
    runner.user_input = [
        UserInput("0", UserInput.COMMAND),
        UserInput("1", UserInput.COMMAND),
        UserInput("2", UserInput.COMMAND)]
    runner.input_num = 3
    assert (tuple(runner.get_user_input()) == (
        UserInput("0", UserInput.COMMAND),
        UserInput("1", UserInput.COMMAND),
        UserInput("2", UserInput.COMMAND)))

    runner.input_num = 2
    assert (tuple(runner.get_user_input()) == (
        UserInput("0", UserInput.COMMAND),
        UserInput("1", UserInput.COMMAND)))

    runner.input_num = 1
    assert (tuple(runner.get_user_input()) == (
        UserInput("0", UserInput.COMMAND),))


def test_runner_get_user_commands():
    runner = libigcc.run.Runner(None, None, None)
    runner.user_input = [
        UserInput("0", UserInput.COMMAND),
        UserInput("1", UserInput.COMMAND),
        UserInput("X", UserInput.INCLUDE),
        UserInput("2", UserInput.COMMAND)]
    runner.input_num = 4
    assert (tuple(runner.get_user_commands()) == ("0", "1", "2"))

    runner.input_num = 2
    assert (tuple(runner.get_user_commands()) == ("0", "1"))

    runner.input_num = 1
    assert (tuple(runner.get_user_commands()) == ("0",))


def test_undo_1():
    commands = [
        'int a;',
        'a = 5;',
        'foobar',
        '.u',
        'cout << a << endl;',
    ]

    expected_output = (
        r'''g++> int a;
        g++> a = 5;
        g++> foobar
        [Compile error - type .e to see it.]
        g++> .u
        [Undone 'foobar'.]
        g++> cout << a << endl;
        5
        g++>
        ''')

    run_program(commands, expected_output)


def test_undo_2():
    commands = [
        'int a = 5;',
        '++a;',
        '++a;',
        '++a;',
        '.u',
        '.u',
        'cout << a << endl;',
    ]

    expected_output = (
        r'''g++> int a = 5;
        g++> ++a;
        g++> ++a;
        g++> ++a;
        g++> .u
        [Undone '++a;'.]
        g++> .u
        [Undone '++a;'.]
        g++> cout << a << endl;
        6
        g++>
        ''')

    run_program(commands, expected_output)


def test_undo_before_beginning():
    commands = [
        'int a = 5;',
        '.u',
        '.u',
        '.u',
        'cout << a << endl;',
        '.u',
        'int b = 7;',
        'cout << b << endl;',
    ]

    expected_output = (
        r'''g++> int a = 5;
        g++> .u
        [Undone 'int a = 5;'.]
        g++> .u
        [Nothing to undo.]
        g++> .u
        [Nothing to undo.]
        g++> cout << a << endl;
        [Compile error - type .e to see it.]
        g++> .u
        [Undone 'cout << a << endl;'.]
        g++> int b = 7;
        g++> cout << b << endl;
        7
        g++>
        ''')

    run_program(commands, expected_output)


def test_undo_includes_and_commands():
    commands = [
        'int a = 5;',
        '#include <vector>',
        '++a;',
        '.u',
        '.u',
        '.u',
    ]

    expected_output = (
        r'''g++> int a = 5;
        g++> #include <vector>
        g++> ++a;
        g++> .u
        [Undone '++a;'.]
        g++> .u
        [Undone '#include <vector>'.]
        g++> .u
        [Undone 'int a = 5;'.]
        g++>
        ''')

    run_program(commands, expected_output)


def test_redo_1():
    commands = [
        'int a = 1;',
        '++a;',
        '.u',
        '.r',
        'cout << a << endl;',
    ]

    expected_output = (
        r'''g++> int a = 1;
        g++> ++a;
        g++> .u
        [Undone '++a;'.]
        g++> .r
        [Redone '++a;'.]
        g++> cout << a << endl;
        2
        g++>
        ''')

    run_program(commands, expected_output)


def test_redo_2():
    commands = [
        'int a = 1;',
        '++a;',
        '.u',
        '.u',
        '.r',
        '.r',
        'cout << a << endl;',
    ]

    expected_output = (
        r'''g++> int a = 1;
        g++> ++a;
        g++> .u
        [Undone '++a;'.]
        g++> .u
        [Undone 'int a = 1;'.]
        g++> .r
        [Redone 'int a = 1;'.]
        g++> .r
        [Redone '++a;'.]
        g++> cout << a << endl;
        2
        g++>
        ''')

    run_program(commands, expected_output)


def test_redo_before_beginning():
    commands = [
        'int a = 1;',
        '++a;',
        '.u',
        '.u',
        '.u',
        '.r',
        '.r',
        'cout << a << endl;',
    ]

    expected_output = (
        r'''g++> int a = 1;
        g++> ++a;
        g++> .u
        [Undone '++a;'.]
        g++> .u
        [Undone 'int a = 1;'.]
        g++> .u
        [Nothing to undo.]
        g++> .r
        [Redone 'int a = 1;'.]
        g++> .r
        [Redone '++a;'.]
        g++> cout << a << endl;
        2
        g++>
        ''')

    run_program(commands, expected_output)


def test_redo_after_end():
    commands = [
        'int a = 1;',
        '++a;',
        '.u',
        '.r',
        '.r',
        'cout << a << endl;',
    ]

    expected_output = (
        r'''g++> int a = 1;
        g++> ++a;
        g++> .u
        [Undone '++a;'.]
        g++> .r
        [Redone '++a;'.]
        g++> .r
        [Nothing to redo.]
        g++> cout << a << endl;
        2
        g++>
        ''')

    run_program(commands, expected_output)


def test_redo_includes_and_commands():
    commands = [
        'int a = 5;',
        '#include <vector>',
        '++a;',
        '.u',
        '.u',
        '.u',
        '.r',
        '.r',
        '.r',
    ]

    expected_output = (
        r'''g++> int a = 5;
        g++> #include <vector>
        g++> ++a;
        g++> .u
        [Undone '++a;'.]
        g++> .u
        [Undone '#include <vector>'.]
        g++> .u
        [Undone 'int a = 5;'.]
        g++> .r
        [Redone 'int a = 5;'.]
        g++> .r
        [Redone '#include <vector>'.]
        g++> .r
        [Redone '++a;'.]
        g++>
        ''')

    run_program(commands, expected_output)


def test_undo_then_new_commands():
    commands = [
        'int a = 5;',
        '++a;',
        '.u',
        '--a;',
        '--a;',
        '.u',
        'cout << a << endl;',
    ]

    expected_output = (
        r'''g++> int a = 5;
        g++> ++a;
        g++> .u
        [Undone '++a;'.]
        g++> --a;
        g++> --a;
        g++> .u
        [Undone '--a;'.]
        g++> cout << a << endl;
        4
        g++>
        ''')

    run_program(commands, expected_output)


def test_undo_redo_with_output():
    commands = [
        'int a = 56;',
        'cout << a << endl;',
        '.u',
        '.r',
        '.u',
        'cout << 12 << endl;',
    ]

    expected_output = (
        r'''g++> int a = 56;
        g++> cout << a << endl;
        56
        g++> .u
        [Undone 'cout << a << endl;'.]
        g++> .r
        [Redone 'cout << a << endl;'.]
        56
        g++> .u
        [Undone 'cout << a << endl;'.]
        g++> cout << 12 << endl;
        12
        g++>
        ''')

    run_program(commands, expected_output)


def test_print_stderr_twice():
    commands = ["int a = 10;",
                'cerr << a << endl;',
                "++a;",
                'cerr << a << endl;']

    expected_output = (
        '''g++> int a = 10;
        g++> cerr << a << endl;
        10
        g++> ++a;
        g++> cerr << a << endl;
        11
        g++>
        ''')

    run_program(commands, expected_output)


def test_print_stderr_stdout():
    commands = ["int a = 10;",
                'cerr << a << endl;',
                "++a;",
                'cout << a << endl;']

    expected_output = (
        '''g++> int a = 10;
        g++> cerr << a << endl;
        10
        g++> ++a;
        g++> cout << a << endl;
        11
        g++>
        ''')

    run_program(commands, expected_output)


def test_undo_stderr_then_new_commands():
    commands = [
        'int a = 5;',
        '++a;',
        '.u',
        '--a;',
        '--a;',
        '.u',
        'cerr << a << endl;',
    ]

    expected_output = (
        r'''g++> int a = 5;
        g++> ++a;
        g++> .u
        [Undone '++a;'.]
        g++> --a;
        g++> --a;
        g++> .u
        [Undone '--a;'.]
        g++> cerr << a << endl;
        4
        g++>
        ''')

    run_program(commands, expected_output)


def main():
    tests = [
        test_declare_var,
        test_declare_var_assign,
        test_declare_and_assign_var_then_print,
        test_print_twice,
        test_compile_error,
        test_compile_error_display,
        test_include,
        test_multiple_repeated_includes,
        test_list_program,
        test_list_full_program,
        test_help_message,
        test_quit,
        test_include_dir_on_cmd_line,
        test_2_include_dirs_on_cmd_line,
        test_lib,
        test_runner_get_user_input,
        test_runner_get_user_commands,
        test_undo_1,
        test_undo_2,
        test_undo_before_beginning,
        test_undo_includes_and_commands,
        test_redo_1,
        test_redo_2,
        test_redo_before_beginning,
        test_redo_after_end,
        test_redo_includes_and_commands,
        test_undo_then_new_commands,
        test_undo_redo_with_output,
        test_print_stderr_twice,
        test_print_stderr_stdout,
        test_undo_stderr_then_new_commands]

    for i, test in enumerate(tests, start=1):
        print(f"Running test {i}/{len(tests)}")
        test()

    # test_readline_history();
    # test_print_command();
    # test_edit_in_vim();
    # test_compile_warning()
    # test_remove_compile_error_message()

    print("All tests passed.")


if __name__ == "__main__":
    main()
