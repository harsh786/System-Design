# Bit Manipulation Patterns

## Decision Flowchart

```
Problem involves integers/binary properties?
├─ "Find unique element" → XOR-based (Patterns 2-4)
├─ "Count bits / bit properties" → DP or Brian Kernighan (Pattern 5)
├─ "Power of 2/4/8" → Single bit check (Pattern 6)
├─ "Distance between bits" → XOR + popcount (Pattern 7)
├─ "Generate all subsets" → Bitmask enumeration (Pattern 8)
├─ "Range operation on bits" → Common prefix (Pattern 9)
├─ "Maximize XOR" → Trie (Pattern 10)
├─ "Sequence with adjacent 1-bit diff" → Gray Code (Pattern 11)
├─ "Reverse/rotate bits" → Divide & conquer swap (Pattern 12)
├─ "Validate bit patterns" → Mask checking (Pattern 13)
└─ "Arithmetic without operators" → Bit shifting (Pattern 14)
```

---

## Two's Complement

```
For n-bit integers:
- Positive numbers: standard binary
- Negative numbers: invert all bits + 1

Example (8-bit):
  5  = 00000101
 -5  = 11111011  (invert 00000101 → 11111010, add 1 → 11111011)

Key properties:
- Range: [-2^(n-1), 2^(n-1) - 1]
- Java int: 32-bit, range [-2^31, 2^31 - 1]
- -x == ~x + 1
- -1 == all 1s (11111111...1)
- Overflow wraps around silently in Java
```

---

## Complete Bitwise Operations Reference

| Operation | Java Syntax | Example (a=0b1010, b=0b1100) | Result |
|-----------|------------|-------------------------------|--------|
| AND | `a & b` | 1010 & 1100 | 1000 |
| OR | `a \| b` | 1010 \| 1100 | 1110 |
| XOR | `a ^ b` | 1010 ^ 1100 | 0110 |
| NOT | `~a` | ~1010 | ...0101 |
| Left Shift | `a << n` | 1010 << 1 | 10100 |
| Right Shift (signed) | `a >> n` | 1010 >> 1 | 0101 |
| Right Shift (unsigned) | `a >>> n` | -1 >>> 30 | 3 |

### Java-Specific Notes

```
>> vs >>>:
  >> : arithmetic shift, preserves sign bit (fills with sign bit)
  >>>: logical shift, fills with 0 (USE for unsigned operations)

  -8 >> 1  = -4    (11111...1000 → 11111...1100)
  -8 >>> 1 = 2147483644  (01111...1100)

int vs long:
  - Bit operations on int: result is int (32-bit)
  - Use 1L << n for shifts > 31
  - (1 << 32) == 1 (wraps!), (1L << 32) == 4294967296

Useful Integer methods:
  Integer.bitCount(n)          // popcount
  Integer.highestOneBit(n)     // isolate MSB
  Integer.lowestOneBit(n)      // isolate LSB (same as n & -n)
  Integer.numberOfLeadingZeros(n)
  Integer.numberOfTrailingZeros(n)
  Integer.reverse(n)           // reverse all 32 bits
  Integer.reverseBytes(n)      // reverse byte order
  Integer.toBinaryString(n)    // string representation
```

---

## Common Bit Tricks

| Trick | Expression | Example (n=0b1010_1100) |
|-------|-----------|------------------------|
| Set bit i | `n \| (1 << i)` | set bit 0: 1010_1101 |
| Clear bit i | `n & ~(1 << i)` | clear bit 2: 1010_1000 |
| Toggle bit i | `n ^ (1 << i)` | toggle bit 0: 1010_1101 |
| Check bit i | `(n >> i) & 1` | check bit 3: 1 |
| Get lowest set bit | `n & (-n)` | 1010_1100 → 0000_0100 |
| Clear lowest set bit | `n & (n - 1)` | 1010_1100 → 1010_1000 |
| Set all bits below MSB | `n \| (n-1)` | 1010_1100 → 1010_1111... |
| Is power of 2 | `n > 0 && (n & (n-1)) == 0` | |
| Count set bits | Brian Kernighan loop | |
| Isolate rightmost 0 | `~n & (n + 1)` | 1010_1100 → 0000_0001 |
| Turn on rightmost 0 | `n \| (n + 1)` | 1010_1100 → 1010_1101 |
| Create mask of i bits | `(1 << i) - 1` | i=4: 0000_1111 |
| Extract bits [i,j] | `(n >> i) & ((1 << (j-i+1)) - 1)` | |
| Swap without temp | `a^=b; b^=a; a^=b;` | |
| Absolute value | `(n ^ (n >> 31)) - (n >> 31)` | (no branch) |
| Min without branch | `b ^ ((a ^ b) & -(a < b ? 1 : 0))` | |
| Modulo 2^k | `n & ((1 << k) - 1)` | same as n % (2^k) |

---

## Pattern 1: Core Bit Operations Cheat Sheet

### Count Set Bits (Brian Kernighan)

```java
// Signal: count number of 1-bits
int countBits(int n) {
    int count = 0;
    while (n != 0) {
        n &= (n - 1);  // clear lowest set bit
        count++;
    }
    return count;
}
// O(k) where k = number of set bits
```

**Visualization:**
```
n = 1011_0100
    1011_0100  & 1011_0011 = 1011_0000  count=1
    1011_0000  & 1010_1111 = 1010_0000  count=2
    1010_0000  & 1001_1111 = 1000_0000  count=3
    1000_0000  & 0111_1111 = 0000_0000  count=4  → done
```

---

## Pattern 2: Single Number (XOR All Elements)

### Signal
- Array where every element appears twice except one. Find the unique one.
- Any "find unpaired" problem.

### Template

```java
public int singleNumber(int[] nums) {
    int result = 0;
    for (int n : nums) {
        result ^= n;
    }
    return result;
}
```

### Visualization

```
nums = [4, 1, 2, 1, 2]

XOR properties: a ^ a = 0, a ^ 0 = a, commutative & associative

result = 4 ^ 1 ^ 2 ^ 1 ^ 2
       = 4 ^ (1 ^ 1) ^ (2 ^ 2)
       = 4 ^ 0 ^ 0
       = 4
```

### Variants
- Find missing number in [0..n]: XOR all indices with all values
- Find duplicate: XOR index range with array values

### Complexity
- Time: O(n), Space: O(1)

---

## Pattern 3: Single Number II (Every Element 3x Except One)

### Signal
- Every element appears k times except one appearing once.
- Generalized: count bits modulo k.

### Template (Bit Counting)

```java
public int singleNumber(int[] nums) {
    int result = 0;
    for (int i = 0; i < 32; i++) {
        int bitSum = 0;
        for (int n : nums) {
            bitSum += (n >> i) & 1;
        }
        if (bitSum % 3 != 0) {
            result |= (1 << i);
        }
    }
    return result;
}
```

### Template (State Machine - O(1) space, single pass)

```java
// ones/twos track bits appearing 1/2 times mod 3
public int singleNumber(int[] nums) {
    int ones = 0, twos = 0;
    for (int n : nums) {
        ones = (ones ^ n) & ~twos;
        twos = (twos ^ n) & ~ones;
    }
    return ones;
}
```

### Visualization

```
State machine for each bit position (mod 3 counter):
  State (ones, twos):
    (0,0) → input 1 → (1,0)  [seen 1 time]
    (1,0) → input 1 → (0,1)  [seen 2 times]
    (0,1) → input 1 → (0,0)  [seen 3 times → reset]

nums = [2, 2, 3, 2]  →  binary: 10, 10, 11, 10
Bit 0: sum = 0+0+1+0 = 1, 1%3 = 1 → set
Bit 1: sum = 1+1+1+1 = 4, 4%3 = 1 → set
Result = 11 = 3
```

### Variants
- Every element k times except one: use mod k counting
- Two elements appear once, rest twice → Pattern 4

### Complexity
- Bit counting: O(32n) time, O(1) space
- State machine: O(n) time, O(1) space

---

## Pattern 4: Single Number III (Two Unique Elements)

### Signal
- Exactly two elements appear once, all others twice.

### Template

```java
public int[] singleNumber(int[] nums) {
    // Step 1: XOR all → gets xor of the two unique numbers
    int xor = 0;
    for (int n : nums) xor ^= n;
    
    // Step 2: Find any bit where they differ (use lowest set bit)
    int diff = xor & (-xor);
    
    // Step 3: Split into two groups and XOR each
    int a = 0, b = 0;
    for (int n : nums) {
        if ((n & diff) == 0) a ^= n;
        else b ^= n;
    }
    return new int[]{a, b};
}
```

### Visualization

```
nums = [1, 2, 1, 3, 2, 5]
Step 1: xor = 1^2^1^3^2^5 = 3^5 = 011^101 = 110 (6)
Step 2: diff = 6 & -6 = 110 & 010 = 010 (bit 1)
Step 3: Split by bit 1:
  Group 0 (bit1=0): [1, 1, 5] → XOR = 5
  Group 1 (bit1=1): [2, 3, 2] → XOR = 3
Result: [5, 3]
```

### Complexity
- Time: O(n), Space: O(1)

---

## Pattern 5: Counting Bits (DP)

### Signal
- Count set bits for every number 0..n.
- Relates to previous results (overlapping subproblems).

### Template

```java
public int[] countBits(int n) {
    int[] dp = new int[n + 1];
    for (int i = 1; i <= n; i++) {
        dp[i] = dp[i >> 1] + (i & 1);
        // OR: dp[i] = dp[i & (i-1)] + 1;  (clear lowest set bit)
    }
    return dp;
}
```

### Visualization

```
i:    0  1  2  3  4  5  6  7  8
bin: 000 001 010 011 100 101 110 111 1000
dp:   0  1  1  2  1  2  2  3  1

dp[5] = dp[5>>1] + (5&1) = dp[2] + 1 = 1 + 1 = 2
dp[6] = dp[6>>1] + (6&1) = dp[3] + 0 = 2 + 0 = 2
```

### Complexity
- Time: O(n), Space: O(n)

---

## Pattern 6: Power of Two / Power of Four

### Signal
- Check if number is an exact power of 2, 4, 8, etc.

### Template

```java
// Power of 2: exactly one bit set
boolean isPowerOfTwo(int n) {
    return n > 0 && (n & (n - 1)) == 0;
}

// Power of 4: one bit set AND that bit is at even position
boolean isPowerOfFour(int n) {
    // 0x55555555 = 0101_0101... (bits at even positions)
    return n > 0 && (n & (n - 1)) == 0 && (n & 0x55555555) != 0;
}

// Alternative: power of 4 means (n-1) % 3 == 0
boolean isPowerOfFourAlt(int n) {
    return n > 0 && (n & (n - 1)) == 0 && (n - 1) % 3 == 0;
}
```

### Visualization

```
Powers of 2:  1, 10, 100, 1000, 10000 ...
Powers of 4:  1(pos0), 100(pos2), 10000(pos4) ...
                  ↑ even positions only

Mask 0x55555555 = ...0101_0101_0101_0101
  16 = 10000  & 0101...0101 = 10000 & 00...10101 = 10000? 
  Wait: pos 4 is even → 10000 & mask ≠ 0 ✓ (16 is power of 4)
  8  = 01000  & mask = 0 (pos 3 is odd) → not power of 4
```

### Complexity
- Time: O(1), Space: O(1)

---

## Pattern 7: Hamming Distance / Total Hamming Distance

### Signal
- Count differing bits between two numbers.
- Sum of pairwise Hamming distances across array.

### Template

```java
// Hamming distance between two numbers
int hammingDistance(int x, int y) {
    return Integer.bitCount(x ^ y);
}

// Total Hamming distance of array (sum all pairs)
int totalHammingDistance(int[] nums) {
    int total = 0, n = nums.length;
    for (int bit = 0; bit < 32; bit++) {
        int ones = 0;
        for (int num : nums) {
            ones += (num >> bit) & 1;
        }
        // ones numbers have 1, (n-ones) have 0 → ones*(n-ones) differing pairs
        total += ones * (n - ones);
    }
    return total;
}
```

### Visualization

```
Total Hamming: nums = [4, 14, 2] = [0100, 1110, 0010]

Bit 0: ones=0, zeros=3 → 0*3 = 0
Bit 1: ones=2(14,2), zeros=1 → 2*1 = 2
Bit 2: ones=2(4,14), zeros=1 → 2*1 = 2
Bit 3: ones=1(14), zeros=2 → 1*2 = 2
Total = 6

Brute force verification: d(4,14)+d(4,2)+d(14,2) = 2+2+2 = 6 ✓
```

### Complexity
- Single pair: O(1)
- Total: O(32n) = O(n) time, O(1) space (vs O(n^2) brute force)

---

## Pattern 8: Subset Enumeration with Bitmask

### Signal
- Generate all subsets of a set.
- Iterate all subsets of a given bitmask.
- DP over subsets (bitmask DP).

### Template

```java
// Generate all 2^n subsets of n elements
List<List<Integer>> subsets(int[] nums) {
    int n = nums.length;
    List<List<Integer>> result = new ArrayList<>();
    for (int mask = 0; mask < (1 << n); mask++) {
        List<Integer> subset = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            if ((mask >> i & 1) == 1) subset.add(nums[i]);
        }
        result.add(subset);
    }
    return result;
}

// Iterate all submasks of a given mask (CRITICAL for bitmask DP)
void iterateSubmasks(int mask) {
    for (int sub = mask; sub > 0; sub = (sub - 1) & mask) {
        // process submask 'sub'
    }
    // don't forget empty subset (sub = 0) if needed
}
```

### Visualization

```
nums = [a, b, c], n = 3

mask  binary  subset
0     000     []
1     001     [a]
2     010     [b]
3     011     [a,b]
4     100     [c]
5     101     [a,c]
6     110     [b,c]
7     111     [a,b,c]

Submasks of mask=0b1010:
  1010 → 1000 → 0010 → 0000(stop)
  Formula: sub = (sub-1) & mask
    1010 - 1 = 1001, & 1010 = 1000
    1000 - 1 = 0111, & 1010 = 0010
    0010 - 1 = 0001, & 1010 = 0000
```

### Variants
- Bitmask DP (TSP, assignment): `dp[mask]` = optimal for visited set `mask`
- Partition into k subsets with equal sum
- Total complexity of iterating all submasks of all masks = O(3^n)

### Complexity
- All subsets: O(2^n * n)
- All submasks of all masks: O(3^n)

---

## Pattern 9: Bitwise AND of Numbers Range

### Signal
- Compute AND of all numbers in [left, right].
- Key insight: AND only preserves common prefix bits.

### Template

```java
public int rangeBitwiseAnd(int left, int right) {
    int shift = 0;
    while (left != right) {
        left >>= 1;
        right >>= 1;
        shift++;
    }
    return left << shift;
}

// Alternative: clear rightmost different bits of right
public int rangeBitwiseAnd2(int left, int right) {
    while (right > left) {
        right &= (right - 1);  // clear lowest set bit
    }
    return right;
}
```

### Visualization

```
left=5 (0101), right=7 (0111)

AND of 5,6,7 = 0101 & 0110 & 0111 = 0100

Finding common prefix:
  0101 >> 1 = 010,  0111 >> 1 = 011  (shift=1)
  010  >> 1 = 01,   011  >> 1 = 01   (shift=2) → equal!
  Result: 01 << 2 = 0100 = 4 ✓

Intuition: between left and right, lower bits will see both 0 and 1,
so they AND to 0. Only the common prefix survives.
```

### Complexity
- Time: O(log n), Space: O(1)

---

## Pattern 10: Maximum XOR (Trie-Based)

### Signal
- Find two elements with maximum XOR.
- Find maximum XOR of element with any previous element.
- XOR queries against a collection.

### Template

```java
class TrieNode {
    TrieNode[] children = new TrieNode[2]; // [0-bit, 1-bit]
}

public int findMaximumXOR(int[] nums) {
    // Build trie of all numbers (MSB to LSB)
    TrieNode root = new TrieNode();
    for (int num : nums) {
        TrieNode node = root;
        for (int i = 31; i >= 0; i--) {
            int bit = (num >> i) & 1;
            if (node.children[bit] == null)
                node.children[bit] = new TrieNode();
            node = node.children[bit];
        }
    }
    
    // For each number, greedily take opposite bit path
    int max = 0;
    for (int num : nums) {
        TrieNode node = root;
        int xor = 0;
        for (int i = 31; i >= 0; i--) {
            int bit = (num >> i) & 1;
            int want = 1 - bit;  // want opposite bit for max XOR
            if (node.children[want] != null) {
                xor |= (1 << i);
                node = node.children[want];
            } else {
                node = node.children[bit];
            }
        }
        max = Math.max(max, xor);
    }
    return max;
}
```

### Visualization

```
nums = [3, 10, 5, 25, 2, 8]

Trie (showing paths for 3=00011, 25=11001):
        root
       /    \
      0      1
     / \      \
    0   ...    1
    |          |
    0          0
    |          |
    1          0
    |          |
    1          1

For num=5 (00101), greedily go opposite:
  bit=0 → want 1, have 1 → go right, xor |= bit31... 
  ...eventually finds 25 for XOR = 00101 ^ 11001 = 11100 = 28

Max XOR = 28 (5 ^ 25)
```

### Variants
- Maximum XOR subarray (use prefix XOR + trie)
- Queries: max XOR with value ≤ limit (augmented trie)
- Persistent trie for range queries

### Complexity
- Time: O(32n) = O(n), Space: O(32n) for trie

---

## Pattern 11: Gray Code Generation

### Signal
- Generate sequence where adjacent elements differ by 1 bit.
- Binary reflected Gray code.

### Template

```java
// Formula: gray(i) = i ^ (i >> 1)
public List<Integer> grayCode(int n) {
    List<Integer> result = new ArrayList<>();
    for (int i = 0; i < (1 << n); i++) {
        result.add(i ^ (i >> 1));
    }
    return result;
}

// Inverse: Gray to binary
int grayToBinary(int gray) {
    int binary = 0;
    while (gray > 0) {
        binary ^= gray;
        gray >>= 1;
    }
    return binary;
}
```

### Visualization

```
n=3:
i   binary  i>>1  gray(i^(i>>1))  binary_gray
0   000     000   000             000
1   001     000   001             001
2   010     001   011             011
3   011     001   010             010
4   100     010   110             110
5   101     010   111             111
6   110     011   101             101
7   111     011   100             100

Adjacent differences (exactly 1 bit):
000→001→011→010→110→111→101→100
    ^1   ^1   ^1   ^1   ^1   ^1   ^1
```

### Complexity
- Time: O(2^n), Space: O(2^n)

---

## Pattern 12: Reverse Bits / Rotate Bits

### Signal
- Reverse all 32 bits of an integer.
- Rotate bits left/right by k positions.

### Template

```java
// Reverse bits of 32-bit integer
public int reverseBits(int n) {
    n = ((n & 0xffff0000) >>> 16) | ((n & 0x0000ffff) << 16);
    n = ((n & 0xff00ff00) >>> 8)  | ((n & 0x00ff00ff) << 8);
    n = ((n & 0xf0f0f0f0) >>> 4)  | ((n & 0x0f0f0f0f) << 4);
    n = ((n & 0xcccccccc) >>> 2)  | ((n & 0x33333333) << 2);
    n = ((n & 0xaaaaaaaa) >>> 1)  | ((n & 0x55555555) << 1);
    return n;
}

// Simple version (loop)
public int reverseBitsSimple(int n) {
    int result = 0;
    for (int i = 0; i < 32; i++) {
        result = (result << 1) | (n & 1);
        n >>>= 1;
    }
    return result;
}

// Rotate left by k (32-bit)
int rotateLeft(int n, int k) {
    k &= 31;
    return (n << k) | (n >>> (32 - k));
}
```

### Visualization

```
Divide & conquer reversal (16-bit example for brevity):
Original:   ABCD EFGH IJKL MNOP

Swap halves (8-bit): IJKL MNOP ABCD EFGH
Swap 4-bit groups:   MNOP IJKL EFGH ABCD
Swap 2-bit pairs:    OPMN KLIJ GHEF CDAB
Swap adjacent bits:  PONM LKJI HGFE DCBA  ✓ reversed
```

### Complexity
- Time: O(1) (fixed 32 bits), Space: O(1)

---

## Pattern 13: UTF-8 Validation

### Signal
- Validate byte sequences against bit-pattern rules.
- Any problem requiring mask-based pattern matching on integers.

### Template

```java
public boolean validUtf8(int[] data) {
    int remaining = 0; // bytes remaining in current character
    
    for (int b : data) {
        b &= 0xFF; // only look at lowest 8 bits
        
        if (remaining == 0) {
            if ((b & 0b10000000) == 0)          remaining = 0; // 0xxxxxxx (1-byte)
            else if ((b & 0b11100000) == 0b11000000) remaining = 1; // 110xxxxx (2-byte)
            else if ((b & 0b11110000) == 0b11100000) remaining = 2; // 1110xxxx (3-byte)
            else if ((b & 0b11111000) == 0b11110000) remaining = 3; // 11110xxx (4-byte)
            else return false;
        } else {
            // Continuation byte must be 10xxxxxx
            if ((b & 0b11000000) != 0b10000000) return false;
            remaining--;
        }
    }
    return remaining == 0;
}
```

### Visualization

```
UTF-8 encoding rules:
  1-byte: 0xxxxxxx                          (ASCII, 0-127)
  2-byte: 110xxxxx 10xxxxxx                  (128-2047)
  3-byte: 1110xxxx 10xxxxxx 10xxxxxx         (2048-65535)
  4-byte: 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx (65536-1114111)

Validation masks:
  Leading byte detection:
    b & 0x80 == 0x00 → 1-byte    (mask: 10000000, expect: 00000000)
    b & 0xE0 == 0xC0 → 2-byte    (mask: 11100000, expect: 11000000)
    b & 0xF0 == 0xE0 → 3-byte    (mask: 11110000, expect: 11100000)
    b & 0xF8 == 0xF0 → 4-byte    (mask: 11111000, expect: 11110000)
  
  Continuation byte:
    b & 0xC0 == 0x80             (mask: 11000000, expect: 10000000)
```

### Complexity
- Time: O(n), Space: O(1)

---

## Pattern 14: Divide Without Division Operator

### Signal
- Implement division using only bit operations and subtraction.
- Any arithmetic through shifting.

### Template

```java
public int divide(int dividend, int divisor) {
    // Handle overflow: -2^31 / -1 = 2^31 (overflow)
    if (dividend == Integer.MIN_VALUE && divisor == -1)
        return Integer.MAX_VALUE;
    
    // Work with positive values using long to avoid overflow
    long a = Math.abs((long) dividend);
    long b = Math.abs((long) divisor);
    int sign = (dividend ^ divisor) < 0 ? -1 : 1;
    
    int result = 0;
    while (a >= b) {
        long temp = b;
        int shift = 0;
        while (a >= (temp << 1)) {
            temp <<= 1;
            shift++;
        }
        a -= temp;
        result += (1 << shift);
    }
    return sign * result;
}
```

### Visualization

```
43 / 5 = 8 remainder 3

a=43, b=5:
  Find largest shift: 5<<3=40 ≤ 43, 5<<4=80 > 43 → shift=3
  a = 43 - 40 = 3, result = 8 (1<<3)
  
  3 < 5 → done
  Result = 8 ✓

Binary perspective:
  43 = 101011
  Repeatedly subtract largest possible (divisor << k):
  101011 - 101000(=40) = 000011, quotient bit at position 3
  Result = 1000 = 8
```

### Variants
- Multiply without * operator: shift and add
- Add without + operator: `sum = a ^ b; carry = (a & b) << 1;` repeat

### Complexity
- Time: O(log^2 n) in worst case, Space: O(1)

---

## Summary Table

| # | Pattern | Key Insight | Time | Space |
|---|---------|-------------|------|-------|
| 1 | Core Ops | `n & (n-1)` clears LSB | O(k) | O(1) |
| 2 | Single Number | XOR cancels pairs | O(n) | O(1) |
| 3 | Single Number II | Bit count mod k | O(n) | O(1) |
| 4 | Single Number III | XOR + split by diff bit | O(n) | O(1) |
| 5 | Counting Bits | `dp[i] = dp[i>>1] + (i&1)` | O(n) | O(n) |
| 6 | Power of 2/4 | Single bit check + position | O(1) | O(1) |
| 7 | Hamming Distance | XOR + per-bit counting | O(n) | O(1) |
| 8 | Subset Enumeration | `sub = (sub-1) & mask` | O(2^n) | O(1) |
| 9 | Range AND | Find common prefix | O(log n) | O(1) |
| 10 | Max XOR | Trie, greedy opposite bit | O(n) | O(n) |
| 11 | Gray Code | `i ^ (i >> 1)` | O(2^n) | O(2^n) |
| 12 | Reverse Bits | Divide & conquer swap | O(1) | O(1) |
| 13 | UTF-8 Validation | Mask & compare patterns | O(n) | O(1) |
| 14 | Divide by Shifting | Subtract largest `d<<k` | O(log^2 n) | O(1) |
