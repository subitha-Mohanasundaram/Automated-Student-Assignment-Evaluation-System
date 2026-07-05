def solve(s: str) -> str:
    # Buggy two_sum: uses wrong index tracking — returns wrong indices
    nums_part, target_part = s.split("|")
    nums = [int(x) for x in nums_part.split()]
    target = int(target_part)

    for i in range(len(nums)):
        for j in range(len(nums)):   # bug: j starts from 0, not i+1 → self-pairs
            if nums[i] + nums[j] == target:
                return f"{i} {j}"
    return ""
