def solve(s: str) -> str:
    nums_part, target_part = s.split("|")
    nums = [int(x) for x in nums_part.split()]
    target = int(target_part)

    seen = {}
    for i, n in enumerate(nums):
        need = target - n
        if need in seen:
            return f"{seen[need]} {i}"
        seen[n] = i
    return ""
