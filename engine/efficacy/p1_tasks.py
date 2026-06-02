"""P1 코드 task 세트 — public(rerank) / hidden(eval) 분리. medium band 위주 (약 base용).

각 task: 함수 시그니처 고정 프롬프트 + public_tests(가시, rerank용) + hidden_tests(은닉, 평가용).
난이도는 qwen2.5:0.5b 기준 (easy=거의 풂 / medium=가끔 / hard=드물게) — lift는 medium에서 기대.
"""

from __future__ import annotations

from engine.efficacy.p1_oracle_rerank_pilot import Task

TASKS = [
    Task(
        "is_palindrome",
        "easy",
        "Write `def is_palindrome(s: str) -> bool:` that returns True iff s reads the same forwards and backwards (case-sensitive, includes all chars).",
        ["assert is_palindrome('aba') == True", "assert is_palindrome('ab') == False"],
        [
            "assert is_palindrome('') == True",
            "assert is_palindrome('a') == True",
            "assert is_palindrome('racecar') == True",
            "assert is_palindrome('abc') == False",
        ],
    ),
    Task(
        "count_vowels",
        "easy",
        "Write `def count_vowels(s: str) -> int:` returning the number of vowels (a,e,i,o,u, case-insensitive) in s.",
        ["assert count_vowels('abc') == 1", "assert count_vowels('AEIOU') == 5"],
        [
            "assert count_vowels('') == 0",
            "assert count_vowels('xyz') == 0",
            "assert count_vowels('Hello World') == 3",
            "assert count_vowels('rhythm') == 0",
        ],
    ),
    Task(
        "gcd",
        "easy",
        "Write `def gcd(a: int, b: int) -> int:` returning the greatest common divisor of a and b (a,b >= 1).",
        ["assert gcd(12, 8) == 4", "assert gcd(7, 1) == 1"],
        [
            "assert gcd(100, 25) == 25",
            "assert gcd(17, 13) == 1",
            "assert gcd(48, 36) == 12",
            "assert gcd(1, 1) == 1",
        ],
    ),
    Task(
        "second_largest",
        "medium",
        "Write `def second_largest(nums: list) -> int:` returning the second largest *distinct* value in nums (len>=2, at least 2 distinct values).",
        ["assert second_largest([1, 2, 3]) == 2", "assert second_largest([5, 5, 4]) == 4"],
        [
            "assert second_largest([10, 10, 9, 8]) == 9",
            "assert second_largest([1, 2]) == 1",
            "assert second_largest([3, 1, 4, 1, 5, 9, 2, 6]) == 6",
            "assert second_largest([-1, -2, -3]) == -2",
        ],
    ),
    Task(
        "balanced_parens",
        "medium",
        "Write `def balanced_parens(s: str) -> bool:` returning True iff every '(' has a matching ')' in correct order. Only parentheses in s.",
        ["assert balanced_parens('()') == True", "assert balanced_parens('(') == False"],
        [
            "assert balanced_parens('') == True",
            "assert balanced_parens('(())') == True",
            "assert balanced_parens(')(') == False",
            "assert balanced_parens('(()') == False",
            "assert balanced_parens('()()') == True",
        ],
    ),
    Task(
        "longest_common_prefix",
        "medium",
        "Write `def longest_common_prefix(strs: list) -> str:` returning the longest common prefix string of all strings in strs ('' if none, strs non-empty).",
        [
            "assert longest_common_prefix(['flower','flow','flight']) == 'fl'",
            "assert longest_common_prefix(['dog','cat']) == ''",
        ],
        [
            "assert longest_common_prefix(['abc']) == 'abc'",
            "assert longest_common_prefix(['','a']) == ''",
            "assert longest_common_prefix(['interspecies','interstellar','interstate']) == 'inters'",
            "assert longest_common_prefix(['same','same']) == 'same'",
        ],
    ),
    Task(
        "flatten",
        "medium",
        "Write `def flatten(lst: list) -> list:` that fully flattens an arbitrarily nested list of ints into a flat list, preserving order.",
        ["assert flatten([1, [2, 3]]) == [1, 2, 3]", "assert flatten([1, [2, [3]]]) == [1, 2, 3]"],
        [
            "assert flatten([]) == []",
            "assert flatten([1, 2, 3]) == [1, 2, 3]",
            "assert flatten([[1], [2], [3]]) == [1, 2, 3]",
            "assert flatten([1, [2, [3, [4, [5]]]]]) == [1, 2, 3, 4, 5]",
        ],
    ),
    Task(
        "roman_to_int",
        "medium",
        "Write `def roman_to_int(s: str) -> int:` converting a valid Roman numeral string (I,V,X,L,C,D,M) to its integer value.",
        ["assert roman_to_int('III') == 3", "assert roman_to_int('IV') == 4"],
        [
            "assert roman_to_int('IX') == 9",
            "assert roman_to_int('LVIII') == 58",
            "assert roman_to_int('MCMXCIV') == 1994",
            "assert roman_to_int('XL') == 40",
        ],
    ),
    Task(
        "merge_sorted",
        "medium",
        "Write `def merge_sorted(a: list, b: list) -> list:` merging two ascending-sorted lists into one ascending-sorted list (keep duplicates).",
        [
            "assert merge_sorted([1, 3], [2, 4]) == [1, 2, 3, 4]",
            "assert merge_sorted([], [1]) == [1]",
        ],
        [
            "assert merge_sorted([], []) == []",
            "assert merge_sorted([1, 1], [1]) == [1, 1, 1]",
            "assert merge_sorted([1, 5, 9], [2, 6]) == [1, 2, 5, 6, 9]",
            "assert merge_sorted([3], [1, 2]) == [1, 2, 3]",
        ],
    ),
    Task(
        "run_length_encode",
        "hard",
        "Write `def run_length_encode(s: str) -> str:` returning run-length encoding: each maximal run of a char c of length n becomes c+str(n). E.g. 'aaab' -> 'a3b1'.",
        ["assert run_length_encode('aaab') == 'a3b1'", "assert run_length_encode('a') == 'a1'"],
        [
            "assert run_length_encode('') == ''",
            "assert run_length_encode('aabbb') == 'a2b3'",
            "assert run_length_encode('abc') == 'a1b1c1'",
            "assert run_length_encode('xxxxx') == 'x5'",
        ],
    ),
    Task(
        "spiral_order",
        "hard",
        "Write `def spiral_order(matrix: list) -> list:` returning all elements of a rectangular 2D list in clockwise spiral order starting top-left.",
        ["assert spiral_order([[1,2],[3,4]]) == [1,2,4,3]", "assert spiral_order([[1]]) == [1]"],
        [
            "assert spiral_order([[1,2,3],[4,5,6],[7,8,9]]) == [1,2,3,6,9,8,7,4,5]",
            "assert spiral_order([[1,2,3,4]]) == [1,2,3,4]",
            "assert spiral_order([[1],[2],[3]]) == [1,2,3]",
        ],
    ),
    Task(
        "int_to_roman",
        "hard",
        "Write `def int_to_roman(n: int) -> str:` converting an integer 1..3999 to its Roman numeral string.",
        ["assert int_to_roman(3) == 'III'", "assert int_to_roman(4) == 'IV'"],
        [
            "assert int_to_roman(9) == 'IX'",
            "assert int_to_roman(58) == 'LVIII'",
            "assert int_to_roman(1994) == 'MCMXCIV'",
            "assert int_to_roman(40) == 'XL'",
        ],
    ),
    Task(
        "two_sum",
        "medium",
        "Write `def two_sum(nums: list, target: int) -> list:` returning indices [i, j] (i<j) such that nums[i]+nums[j]==target. Exactly one solution exists.",
        ["assert two_sum([2,7,11,15], 9) == [0,1]", "assert two_sum([3,2,4], 6) == [1,2]"],
        [
            "assert two_sum([3,3], 6) == [0,1]",
            "assert two_sum([1,2,3,4], 7) == [2,3]",
            "assert two_sum([0,4,3,0], 0) == [0,3]",
        ],
    ),
    Task(
        "is_anagram",
        "easy",
        "Write `def is_anagram(a: str, b: str) -> bool:` returning True iff a and b are anagrams (same chars, same counts).",
        ["assert is_anagram('listen','silent') == True", "assert is_anagram('a','b') == False"],
        [
            "assert is_anagram('','') == True",
            "assert is_anagram('rat','car') == False",
            "assert is_anagram('anagram','nagaram') == True",
            "assert is_anagram('aab','abb') == False",
        ],
    ),
    Task(
        "max_subarray",
        "hard",
        "Write `def max_subarray(nums: list) -> int:` returning the largest sum of any contiguous non-empty subarray (Kadane).",
        ["assert max_subarray([1, 2, 3]) == 6", "assert max_subarray([-1, -2]) == -1"],
        [
            "assert max_subarray([-2,1,-3,4,-1,2,1,-5,4]) == 6",
            "assert max_subarray([5]) == 5",
            "assert max_subarray([-1, 0, -2]) == 0",
            "assert max_subarray([1,-1,1,-1,1]) == 1",
        ],
    ),
]
