# 38 - Math, Combinatorics, and Number Theory

## Decision Flowchart

```
Input constraint n ≤ 10^9 but expected O(log n) or O(1)?
├── Involves power/exponent → Fast Exponentiation (#3)
├── Count primes up to n → Sieve (#2)
├── GCD/LCM needed → Euclidean (#1)
├── "How many ways" / counting → Combinatorics (#5) or Catalan (#6)
├── Fibonacci-like recurrence → Matrix Exponentiation (#7)
├── Remainder with multiple mods → CRT (#9)
├── Cycle in digit/number sequence → Floyd's (#11)
└── n ≤ 10^18, answer mod 10^9+7 → Modular Arithmetic (#4)

Input is "nth ugly/super ugly number"? → Multi-pointer/Heap (#17)
"Random with weight"? → Prefix sum + binary search (#15)
"Convert number to words/roman"? → Greedy decomposition (#18)
```

---

## Overflow Prevention Patterns (Java)

```java
// RULE 1: Cast before multiplication
long product = (long) a * b;  // NOT (long)(a * b) — overflow already happened

// RULE 2: Mod at every step
long result = ((long) a * b) % MOD;
// For addition: (a % MOD + b % MOD) % MOD
// For subtraction: ((a % MOD - b % MOD) + MOD) % MOD  // avoid negative

// RULE 3: Use Math.addExact / Math.multiplyExact to detect overflow
try { int r = Math.multiplyExact(a, b); } catch (ArithmeticException e) { /* overflow */ }

// RULE 4: For pow(x, n) with negative n, handle Integer.MIN_VALUE
// -Integer.MIN_VALUE overflows int; cast to long first
long N = n;  // then negate if needed

// RULE 5: Mid calculation without overflow
int mid = left + (right - left) / 2;  // NOT (left + right) / 2
```

---

## Common Formulas Cheat Sheet

| Formula | Expression |
|---------|-----------|
| Sum 1..n | n*(n+1)/2 |
| Sum of squares 1^2..n^2 | n*(n+1)*(2n+1)/6 |
| Sum of cubes 1^3..n^3 | [n*(n+1)/2]^2 |
| Geometric series a + ar + ... + ar^(n-1) | a*(r^n - 1)/(r - 1) |
| Number of divisors of n = p1^a1 * p2^a2... | (a1+1)*(a2+1)*... |
| Euler's totient phi(n) = n * prod(1 - 1/p) for prime p|n | |
| Catalan(n) | C(2n,n)/(n+1) |
| Derangements D(n) | n! * sum_{i=0}^{n} (-1)^i / i! |
| Stirling approx ln(n!) | n*ln(n) - n |

---

## When to Suspect a Math Pattern

1. **Constraints say n ≤ 10^9** but time limit is generous — can't iterate n, need formula
2. **"Count the number of..."** with huge input — combinatorics or DP with math
3. **Answer modulo 10^9+7** — signals large numbers, use modular arithmetic
4. **Sequence/recurrence relation** — matrix exponentiation for O(log n)
5. **"Divisible by", "factors", "primes"** — number theory
6. **Cycle detection in numeric process** — Floyd's algorithm

---

## Pattern 1: GCD / LCM (Euclidean Algorithm)

### Signal
- "Greatest common divisor", "reduce fraction", "largest tile size", "LCM of array"

### Template

```java
// Iterative Euclidean GCD — O(log(min(a,b)))
public int gcd(int a, int b) {
    while (b != 0) {
        int temp = b;
        b = a % b;
        a = temp;
    }
    return a;
}

// LCM using GCD (overflow-safe)
public long lcm(long a, long b) {
    return a / gcd(a, b) * b;  // divide first to avoid overflow
}

// GCD of an array
public int gcdArray(int[] arr) {
    int result = arr[0];
    for (int i = 1; i < arr.length; i++) {
        result = gcd(result, arr[i]);
        if (result == 1) return 1;  // early termination
    }
    return result;
}

// Extended Euclidean: finds x, y such that ax + by = gcd(a,b)
// Returns gcd; x[0] and y[0] hold the coefficients
public int extGcd(int a, int b, int[] x, int[] y) {
    if (b == 0) { x[0] = 1; y[0] = 0; return a; }
    int[] x1 = new int[1], y1 = new int[1];
    int g = extGcd(b, a % b, x1, y1);
    x[0] = y1[0];
    y[0] = x1[0] - (a / b) * y1[0];
    return g;
}
```

### Key Insight
- `gcd(a, b) = gcd(b, a % b)` — reduces problem size logarithmically
- `lcm(a, b) = a * b / gcd(a, b)` — always divide first to prevent overflow
- Extended GCD is foundation for modular inverse

### Variants
- GCD of array: fold left with gcd
- LCM of array: fold left with lcm (watch for overflow — use long)
- Bezout's identity: `ax + by = gcd(a,b)` always has integer solutions

### Complexity
- Time: O(log(min(a,b)))
- Space: O(1) iterative, O(log(min(a,b))) recursive

---

## Pattern 2: Sieve of Eratosthenes

### Signal
- "Count primes less than n", "smallest/largest prime factor", "all primes up to N"
- N ≤ 10^7 (sieve fits in memory)

### Template

```java
// Basic sieve — count primes < n
public int countPrimes(int n) {
    if (n <= 2) return 0;
    boolean[] notPrime = new boolean[n];
    notPrime[0] = notPrime[1] = true;
    for (int i = 2; (long) i * i < n; i++) {
        if (!notPrime[i]) {
            for (int j = i * i; j < n; j += i) {
                notPrime[j] = true;
            }
        }
    }
    int count = 0;
    for (int i = 2; i < n; i++) if (!notPrime[i]) count++;
    return count;
}

// Smallest Prime Factor (SPF) sieve — enables O(log n) factorization
public int[] spfSieve(int n) {
    int[] spf = new int[n + 1];
    for (int i = 0; i <= n; i++) spf[i] = i;
    for (int i = 2; (long) i * i <= n; i++) {
        if (spf[i] == i) { // i is prime
            for (int j = i * i; j <= n; j += i) {
                if (spf[j] == j) spf[j] = i;
            }
        }
    }
    return spf;
}

// Factorize using SPF in O(log n)
public List<Integer> factorize(int x, int[] spf) {
    List<Integer> factors = new ArrayList<>();
    while (x > 1) {
        factors.add(spf[x]);
        x /= spf[x];
    }
    return factors;
}
```

### Key Insight
- Start marking from i*i (smaller multiples already marked by smaller primes)
- Cast `i * i` to long to avoid overflow when i is large
- SPF sieve gives O(log n) factorization after O(n log log n) precomputation

### Variants
- **Segmented sieve**: for ranges [L, R] where R ≤ 10^12 but R-L ≤ 10^6
- **Linear sieve**: O(n) — each composite marked exactly once
- **Bitwise sieve**: pack booleans into bits for 8x memory savings

### Complexity
- Time: O(n log log n)
- Space: O(n)

---

## Pattern 3: Fast Exponentiation / Modular Pow

### Signal
- "Compute a^b mod m", any problem requiring power with large exponent
- Constraints with exponent ≤ 10^18

### Template

```java
// Iterative binary exponentiation — O(log b)
public long modPow(long base, long exp, long mod) {
    long result = 1;
    base %= mod;
    if (base < 0) base += mod;  // handle negative base
    while (exp > 0) {
        if ((exp & 1) == 1) {
            result = result * base % mod;
        }
        base = base * base % mod;
        exp >>= 1;
    }
    return result;
}

// When mod is large and base*base can overflow long (mod > ~3*10^9)
// Use BigInteger or multiply with overflow detection
public long mulMod(long a, long b, long mod) {
    return Math.floorMod(Math.multiplyHigh(a, b), mod);  // Java 9+
    // Alternative: use __int128 in C++, or split into 32-bit halves
}
```

### Key Insight
- Decompose exponent in binary: a^13 = a^8 * a^4 * a^1
- At each step, square the base and halve the exponent
- Always mod after each multiplication to keep numbers small

### Variants
- **Modular inverse** (when mod is prime): a^(-1) = a^(mod-2) mod mod (Fermat's)
- **Power without mod**: use BigInteger for arbitrary precision
- **Towers of exponents** (a^b^c): use Euler's theorem to reduce

### Complexity
- Time: O(log b)
- Space: O(1)

---

## Pattern 4: Modular Arithmetic

### Signal
- "Answer modulo 10^9 + 7", large counting problems, division under mod

### Template

```java
static final long MOD = 1_000_000_007;

// Modular addition (handles negative)
public long modAdd(long a, long b) {
    return ((a % MOD) + (b % MOD)) % MOD;
}

// Modular subtraction
public long modSub(long a, long b) {
    return ((a % MOD) - (b % MOD) + MOD) % MOD;
}

// Modular multiplication
public long modMul(long a, long b) {
    return (a % MOD) * (b % MOD) % MOD;
}

// Modular inverse using Fermat's little theorem (MOD must be prime)
public long modInverse(long a, long mod) {
    return modPow(a, mod - 2, mod);
}

// Modular division: a / b mod p = a * b^(-1) mod p
public long modDiv(long a, long b) {
    return modMul(a, modInverse(b, MOD));
}

// Precompute factorials and inverse factorials for nCr queries
long[] fact, invFact;
public void precompute(int n) {
    fact = new long[n + 1];
    invFact = new long[n + 1];
    fact[0] = 1;
    for (int i = 1; i <= n; i++) fact[i] = fact[i - 1] * i % MOD;
    invFact[n] = modPow(fact[n], MOD - 2, MOD);
    for (int i = n - 1; i >= 0; i--) invFact[i] = invFact[i + 1] * (i + 1) % MOD;
}

public long nCr(int n, int r) {
    if (r < 0 || r > n) return 0;
    return fact[n] % MOD * invFact[r] % MOD * invFact[n - r] % MOD;
}
```

### Key Insight
- **Fermat's little theorem**: a^(p-1) = 1 (mod p) for prime p, so a^(-1) = a^(p-2) mod p
- Division is multiplication by modular inverse — NEVER do integer division then mod
- Precompute factorial + inverse factorial for O(1) nCr queries
- Inverse factorial trick: compute invFact[n] once, then invFact[i] = invFact[i+1] * (i+1)

### Properties
```
(a + b) % m = ((a % m) + (b % m)) % m
(a * b) % m = ((a % m) * (b % m)) % m
(a - b) % m = ((a % m) - (b % m) + m) % m   // +m prevents negative
(a / b) % m = (a * modInverse(b, m)) % m     // only when gcd(b,m)=1
```

### Complexity
- Precomputation: O(n + log MOD)
- Each nCr query: O(1)

---

## Pattern 5: Combinatorics - nCr / nPr

### Signal
- "How many ways to choose", "combinations", "binomial coefficient"
- Small n (≤5000): Pascal's triangle DP
- Large n (≤10^6): factorial + modular inverse

### Template

```java
// Pascal's Triangle DP — no modular inverse needed, works with any mod
public long[][] pascalTriangle(int n) {
    long[][] C = new long[n + 1][n + 1];
    for (int i = 0; i <= n; i++) {
        C[i][0] = 1;
        for (int j = 1; j <= i; j++) {
            C[i][j] = (C[i - 1][j - 1] + C[i - 1][j]) % MOD;
        }
    }
    return C;
}

// For large n with prime mod — use precomputed factorials (Pattern #4)
// nPr = n! / (n-r)!
public long nPr(int n, int r) {
    if (r > n) return 0;
    return fact[n] % MOD * invFact[n - r] % MOD;
}

// Stars and Bars: ways to put n identical items into k bins
// = C(n + k - 1, k - 1)
public long starsAndBars(int n, int k) {
    return nCr(n + k - 1, k - 1);
}

// Multinomial coefficient: n! / (k1! * k2! * ... * km!)
public long multinomial(int n, int[] groups) {
    long result = fact[n];
    for (int k : groups) {
        result = result % MOD * invFact[k] % MOD;
    }
    return result;
}
```

### Key Insight
- Pascal's: C(n,r) = C(n-1,r-1) + C(n-1,r) — no division needed
- For large n with prime mod: use factorial approach from Pattern #4
- **Lucas' theorem**: for nCr mod small prime p, decompose n and r in base p

### Variants
- **Inclusion-exclusion**: count A∪B∪C = |A|+|B|+|C| - |A∩B| - ... + |A∩B∩C|
- **Derangements**: D(n) = (n-1) * (D(n-1) + D(n-2))
- **Pigeonhole principle**: if n+1 items in n boxes, some box has ≥ 2

### Complexity
- Pascal's: O(n^2) time, O(n^2) space
- Factorial method: O(n) precomputation, O(1) per query

---

## Pattern 6: Catalan Numbers

### Signal
- "Number of valid parentheses", "number of BSTs with n nodes"
- "Number of ways to triangulate polygon", "Dyck paths"
- Answer for n=1..5 is 1,2,5,14,42

### Template

```java
// Catalan(n) = C(2n, n) / (n+1) = C(2n, n) - C(2n, n+1)
// Using modular arithmetic for large n
public long catalan(int n) {
    // C(2n, n) * modInverse(n+1)
    return nCr(2 * n, n) % MOD * modInverse(n + 1, MOD) % MOD;
}

// DP approach: C(n) = sum_{i=0}^{n-1} C(i) * C(n-1-i)
public long[] catalanDP(int n) {
    long[] dp = new long[n + 1];
    dp[0] = dp[1] = 1;
    for (int i = 2; i <= n; i++) {
        for (int j = 0; j < i; j++) {
            dp[i] = (dp[i] + dp[j] * dp[i - 1 - j]) % MOD;
        }
    }
    return dp;
}
```

### Key Insight
- Catalan appears whenever you have a recursive structure that splits into left/right
- C(n) = C(2n,n)/(n+1) — use modular inverse for the division
- DP recurrence mirrors: pick root/split point, multiply left * right subproblem counts

### Applications
- Valid parentheses sequences of length 2n
- Number of structurally unique BSTs with n nodes
- Number of full binary trees with n+1 leaves
- Triangulations of (n+2)-gon
- Non-crossing partitions

### Complexity
- Formula: O(n) with precomputed factorials
- DP: O(n^2)

---

## Pattern 7: Fibonacci & Matrix Exponentiation

### Signal
- "nth Fibonacci in O(log n)", any linear recurrence with large n (≤ 10^18)
- "Climbing stairs" with large n, "tiling" problems

### Template

```java
// Matrix multiplication for 2x2 matrices
static final long MOD = 1_000_000_007;

public long[][] matMul(long[][] A, long[][] B) {
    int n = A.length;
    long[][] C = new long[n][n];
    for (int i = 0; i < n; i++)
        for (int k = 0; k < n; k++)
            if (A[i][k] != 0)
                for (int j = 0; j < n; j++)
                    C[i][j] = (C[i][j] + A[i][k] * B[k][j]) % MOD;
    return C;
}

// Matrix exponentiation
public long[][] matPow(long[][] M, long p) {
    int n = M.length;
    long[][] result = new long[n][n];
    for (int i = 0; i < n; i++) result[i][i] = 1; // identity
    while (p > 0) {
        if ((p & 1) == 1) result = matMul(result, M);
        M = matMul(M, M);
        p >>= 1;
    }
    return result;
}

// O(log n) Fibonacci
public long fibonacci(long n) {
    if (n <= 1) return n;
    long[][] M = {{1, 1}, {1, 0}};
    long[][] result = matPow(M, n - 1);
    return result[0][0]; // F(n) = M^(n-1)[0][0] * F(1) + M^(n-1)[0][1] * F(0)
}

// General linear recurrence: f(n) = c1*f(n-1) + c2*f(n-2) + ... + ck*f(n-k)
// Build k×k companion matrix, exponentiate to n-k
```

### Key Insight
- Any linear recurrence can be expressed as matrix multiplication
- Matrix exponentiation gives O(k^3 * log n) for k-th order recurrence
- Fibonacci: [F(n+1), F(n)] = [[1,1],[1,0]]^n * [F(1), F(0)]

### Variants
- **Tribonacci**: 3x3 matrix
- **Tiling problems**: express as recurrence, use matrix expo
- **Graph paths**: A^k[i][j] = number of paths of length k from i to j

### Complexity
- Time: O(k^3 * log n) where k = recurrence order
- Space: O(k^2)

---

## Pattern 8: Integer Factorization

### Signal
- "Find all prime factors", "count divisors", "sum of divisors"
- n ≤ 10^12 (trial division suffices), n ≤ 10^18 (need Pollard's rho)

### Template

```java
// Trial division — O(sqrt(n))
public List<long[]> factorize(long n) {
    List<long[]> factors = new ArrayList<>(); // [prime, exponent]
    for (long p = 2; p * p <= n; p++) {
        if (n % p == 0) {
            int exp = 0;
            while (n % p == 0) { n /= p; exp++; }
            factors.add(new long[]{p, exp});
        }
    }
    if (n > 1) factors.add(new long[]{n, 1});
    return factors;
}

// Count all divisors from prime factorization
public long countDivisors(long n) {
    long count = 1;
    for (long p = 2; p * p <= n; p++) {
        int exp = 0;
        while (n % p == 0) { n /= p; exp++; }
        count *= (exp + 1);
    }
    if (n > 1) count *= 2;
    return count;
}

// Sum of all divisors: product of (p^(e+1) - 1) / (p - 1) for each prime factor
// Get all divisors (small n only)
public List<Integer> getDivisors(int n) {
    List<Integer> divs = new ArrayList<>();
    for (int i = 1; (long) i * i <= n; i++) {
        if (n % i == 0) {
            divs.add(i);
            if (i != n / i) divs.add(n / i);
        }
    }
    Collections.sort(divs);
    return divs;
}
```

### Key Insight
- Only need to check up to sqrt(n) — if no factor found, n is prime
- After trial division, if n > 1, the remaining n is itself a prime factor
- For very large n: Pollard's rho gives expected O(n^(1/4)) with birthday paradox

### Pollard's Rho (Concept)
```java
// Pseudocode for n > 10^12
// 1. Check small primes, perfect powers
// 2. f(x) = (x*x + c) % n (pseudo-random)
// 3. Floyd's cycle: slow = f(slow), fast = f(f(fast))
// 4. d = gcd(|slow - fast|, n); if 1 < d < n, d is a factor
// 5. Repeat with different c if d == n
```

### Complexity
- Trial division: O(sqrt(n))
- Pollard's rho: O(n^(1/4)) expected
- SPF sieve factorization: O(log n) per query after O(n log log n) precomputation

---

## Pattern 9: Chinese Remainder Theorem

### Signal
- "Find x such that x ≡ a1 (mod m1), x ≡ a2 (mod m2), ..."
- Multiple modular constraints, pairwise coprime moduli

### Template

```java
// CRT for two equations: x ≡ a1 (mod m1), x ≡ a2 (mod m2)
// Returns [remainder, lcm(m1,m2)] or null if no solution
public long[] crt2(long a1, long m1, long a2, long m2) {
    // Extended gcd: find p such that m1*p + m2*q = g
    int[] x = new int[1], y = new int[1];
    long g = extGcd((int) m1, (int) m2, x, y);
    if ((a2 - a1) % g != 0) return null; // no solution
    long lcm = m1 / g * m2;
    long diff = (a2 - a1) / g;
    long mod = m2 / g;
    long p = (long) x[0] % mod * (diff % mod) % mod;
    long result = (a1 + m1 * p % lcm + lcm) % lcm;
    return new long[]{result, lcm};
}

// CRT for multiple equations (iterative)
public long[] crt(long[] remainders, long[] moduli) {
    long curR = remainders[0], curM = moduli[0];
    for (int i = 1; i < remainders.length; i++) {
        long[] res = crt2(curR, curM, remainders[i], moduli[i]);
        if (res == null) return null;
        curR = res[0];
        curM = res[1];
    }
    return new long[]{curR, curM};
}
```

### Key Insight
- If moduli are pairwise coprime, unique solution exists mod (m1*m2*...*mk)
- Iteratively combine pairs of equations
- Useful for reconstructing a number from its remainders mod different primes

### Applications
- Reconstruct large numbers from modular residues
- Speed up computation by splitting into smaller moduli
- Problems where constraints are given mod different values

### Complexity
- Time: O(k * log(max_modulus)) where k = number of equations

---

## Pattern 10: Euler's Totient Function

### Signal
- "Count numbers ≤ n coprime to n", "Euler's phi", "multiplicative order"
- Used internally by modular exponentiation generalizations

### Template

```java
// Single value phi(n) — O(sqrt(n))
public long eulerPhi(long n) {
    long result = n;
    for (long p = 2; p * p <= n; p++) {
        if (n % p == 0) {
            while (n % p == 0) n /= p;
            result -= result / p;
        }
    }
    if (n > 1) result -= result / n;
    return result;
}

// Sieve of phi for all values 1..n — O(n log log n)
public int[] phiSieve(int n) {
    int[] phi = new int[n + 1];
    for (int i = 0; i <= n; i++) phi[i] = i;
    for (int i = 2; i <= n; i++) {
        if (phi[i] == i) { // i is prime
            for (int j = i; j <= n; j += i) {
                phi[j] -= phi[j] / i;
            }
        }
    }
    return phi;
}
```

### Key Insight
- phi(n) = n * product(1 - 1/p) for all prime p dividing n
- Multiplicative: phi(a*b) = phi(a)*phi(b) when gcd(a,b)=1
- **Euler's theorem**: a^phi(n) ≡ 1 (mod n) when gcd(a,n)=1
  - Generalizes Fermat's little theorem (phi(p) = p-1 for prime p)

### Applications
- Count fractions a/b in lowest terms where b ≤ n
- Reduce exponents: a^k mod n = a^(k mod phi(n)) mod n (when gcd(a,n)=1)
- RSA cryptography

### Complexity
- Single value: O(sqrt(n))
- Sieve: O(n log log n)

---

## Pattern 11: Happy Number / Digit Sum Patterns

### Signal
- "Is this a happy number?", "digital root", "repeated digit operations"
- Any process that repeatedly transforms a number — detect cycle

### Template

```java
// Happy Number: repeatedly sum squares of digits; happy if reaches 1
public boolean isHappy(int n) {
    int slow = n, fast = n;
    do {
        slow = digitSquareSum(slow);
        fast = digitSquareSum(digitSquareSum(fast));
    } while (slow != fast);
    return slow == 1;
}

private int digitSquareSum(int n) {
    int sum = 0;
    while (n > 0) {
        int d = n % 10;
        sum += d * d;
        n /= 10;
    }
    return sum;
}

// Alternative: HashSet approach (simpler but O(n) space)
public boolean isHappySet(int n) {
    Set<Integer> seen = new HashSet<>();
    while (n != 1 && seen.add(n)) {
        n = digitSquareSum(n);
    }
    return n == 1;
}

// Digital Root: repeated digit sum until single digit
// Formula: digitalRoot(n) = 1 + (n-1) % 9  (for n > 0)
public int digitalRoot(int n) {
    return n == 0 ? 0 : 1 + (n - 1) % 9;
}
```

### Key Insight
- Floyd's cycle detection works because the sequence is bounded
  - For digit square sum: max value for int is bounded by 9^2 * 10 = 810
- Digital root has a direct formula — no iteration needed
- Any bounded deterministic process must eventually cycle

### Variants
- Add digits until single digit (digital root)
- Multiply digits until single digit (multiplicative persistence)
- Collatz conjecture (no proven cycle detection, but can simulate)

### Complexity
- Floyd's: O(cycle length) time, O(1) space
- HashSet: O(cycle length) time and space

---

## Pattern 12: Pow(x, n) Edge Cases

### Signal
- LeetCode 50 "Pow(x, n)", handle negative exponent and overflow

### Template

```java
public double myPow(double x, int n) {
    long N = n;  // CRITICAL: handle Integer.MIN_VALUE
    if (N < 0) {
        x = 1 / x;
        N = -N;
    }
    double result = 1.0;
    while (N > 0) {
        if ((N & 1) == 1) result *= x;
        x *= x;
        N >>= 1;
    }
    return result;
}
```

### Key Insight
- `n = Integer.MIN_VALUE` → `-n` overflows int! Always cast to long first
- `x = 0` with negative n → infinity (undefined), typically return 0
- `x = 1` → always 1 regardless of n
- `x = -1` → depends on parity of n

### Edge Cases Checklist
1. n = 0 → return 1
2. n = Integer.MIN_VALUE → cast to long before negating
3. x = 0, n < 0 → handle as special case
4. x = 1 or x = -1 → short circuit

### Complexity
- Time: O(log |n|)
- Space: O(1)

---

## Pattern 13: Sqrt(x) Without Library

### Signal
- "Integer square root", "compute floor(sqrt(x))"

### Template

```java
// Binary search approach
public int mySqrt(int x) {
    if (x < 2) return x;
    long lo = 1, hi = x / 2;  // sqrt(x) ≤ x/2 for x ≥ 4
    while (lo <= hi) {
        long mid = lo + (hi - lo) / 2;
        long sq = mid * mid;
        if (sq == x) return (int) mid;
        else if (sq < x) lo = mid + 1;
        else hi = mid - 1;
    }
    return (int) hi;
}

// Newton's method (faster convergence)
public int mySqrtNewton(int x) {
    if (x < 2) return x;
    long r = x;
    while (r * r > x) {
        r = (r + x / r) / 2;
    }
    return (int) r;
}
```

### Key Insight
- Binary search: invariant is lo^2 ≤ x < (hi+1)^2
- Newton's: converges quadratically, x_{n+1} = (x_n + a/x_n) / 2
- Use `long` for mid*mid to avoid overflow with large int inputs

### Variants
- Cube root: binary search similarly, or Newton's with x_{n+1} = (2*x_n + a/x_n^2) / 3
- Check perfect square: compute sqrt and verify sqrt*sqrt == x

### Complexity
- Binary search: O(log x)
- Newton's: O(log x) (quadratic convergence means ~log(log(x)) iterations in practice)

---

## Pattern 14: Count Trailing Zeros in Factorial

### Signal
- "Trailing zeros in n!", "how many times does 10 divide n!"

### Template

```java
// Count trailing zeros = count factors of 5 in n!
// (factors of 2 always exceed factors of 5)
public int trailingZeroes(int n) {
    int count = 0;
    while (n >= 5) {
        n /= 5;
        count += n;
    }
    return count;
}

// Generalized: count factor p in n!  (Legendre's formula)
public long factorInFactorial(long n, long p) {
    long count = 0;
    long power = p;
    while (power <= n) {
        count += n / power;
        power *= p;
    }
    return count;
}
```

### Key Insight
- Trailing zeros = min(count_2, count_5) in factorization of n! = count_5
- n/5 + n/25 + n/125 + ... counts multiples of 5, 25, 125, etc.
- Legendre's formula: exponent of prime p in n! = sum_{i=1}^{inf} floor(n/p^i)

### Variants
- Count trailing zeros in base b: factorize b, find limiting prime factor
- "Is n! divisible by k?": factorize k, check each prime's exponent

### Complexity
- Time: O(log_5(n)) = O(log n)
- Space: O(1)

---

## Pattern 15: Random Pick with Weight

### Signal
- "Random pick proportional to weight", "weighted random selection"
- Prefix sum + binary search for O(log n) per pick

### Template

```java
class WeightedRandom {
    int[] prefixSum;
    Random rand;
    
    public WeightedRandom(int[] w) {
        rand = new Random();
        prefixSum = new int[w.length];
        prefixSum[0] = w[0];
        for (int i = 1; i < w.length; i++) {
            prefixSum[i] = prefixSum[i - 1] + w[i];
        }
    }
    
    public int pickIndex() {
        int target = rand.nextInt(prefixSum[prefixSum.length - 1]) + 1;
        // Binary search for leftmost index where prefixSum[i] >= target
        int lo = 0, hi = prefixSum.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (prefixSum[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }
}
```

### Key Insight
- Build prefix sum of weights; total weight = prefixSum[n-1]
- Generate random in [1, totalWeight], binary search for the bucket
- Each index i is selected with probability w[i] / totalWeight

### Variants
- **Reservoir sampling**: weighted random from stream
- **Alias method**: O(1) per pick after O(n) preprocessing

### Complexity
- Build: O(n)
- Pick: O(log n)
- Space: O(n)

---

## Pattern 16: Josephus Problem

### Signal
- "N people in circle, eliminate every k-th, find survivor"
- "Last remaining number in circular elimination"

### Template

```java
// O(n) iterative DP — 0-indexed survivor position
public int josephus(int n, int k) {
    int survivor = 0; // base case: 1 person, position 0
    for (int i = 2; i <= n; i++) {
        survivor = (survivor + k) % i;
    }
    return survivor; // 0-indexed; add 1 for 1-indexed
}

// Recursive (same logic)
public int josephusRecursive(int n, int k) {
    if (n == 1) return 0;
    return (josephusRecursive(n - 1, k) + k) % n;
}

// O(k log n) for large n, small k — skip ahead when k < n
// (advanced variant, rarely needed in interviews)
```

### Key Insight
- After eliminating one person, relabel positions → subproblem of size n-1
- J(n, k) = (J(n-1, k) + k) % n — the +k accounts for the shift after elimination
- 0-indexed result; convert to 1-indexed by adding 1

### Complexity
- Time: O(n)
- Space: O(1) iterative, O(n) recursive

---

## Pattern 17: Ugly Numbers / Super Ugly

### Signal
- "nth number whose only prime factors are 2, 3, 5"
- "nth number divisible only by primes in given set"

### Template

```java
// Ugly Number II: factors are only 2, 3, 5
public int nthUglyNumber(int n) {
    int[] ugly = new int[n];
    ugly[0] = 1;
    int i2 = 0, i3 = 0, i5 = 0;
    
    for (int i = 1; i < n; i++) {
        int next2 = ugly[i2] * 2;
        int next3 = ugly[i3] * 3;
        int next5 = ugly[i5] * 5;
        
        ugly[i] = Math.min(next2, Math.min(next3, next5));
        
        if (ugly[i] == next2) i2++;
        if (ugly[i] == next3) i3++;
        if (ugly[i] == next5) i5++;
    }
    return ugly[n - 1];
}

// Super Ugly: given list of primes
public int nthSuperUglyNumber(int n, int[] primes) {
    int[] ugly = new int[n];
    ugly[0] = 1;
    int[] idx = new int[primes.length]; // pointer for each prime
    
    for (int i = 1; i < n; i++) {
        ugly[i] = Integer.MAX_VALUE;
        for (int j = 0; j < primes.length; j++) {
            ugly[i] = Math.min(ugly[i], ugly[idx[j]] * primes[j]);
        }
        for (int j = 0; j < primes.length; j++) {
            if (ugly[i] == ugly[idx[j]] * primes[j]) idx[j]++;
        }
    }
    return ugly[n - 1];
}
```

### Key Insight
- Each ugly number is a previous ugly number multiplied by one of the primes
- Multi-pointer approach: each prime has its own pointer into the ugly array
- Advance ALL pointers that match (handles duplicates like 2*3 = 3*2 = 6)

### Variants
- **Heap approach**: push prime*ugly[i] into min-heap, deduplicate
- **Ugly Number I**: just check if n's only factors are 2,3,5 — divide out repeatedly

### Complexity
- Multi-pointer: O(n * k) where k = number of primes
- Heap: O(n * log k)
- Space: O(n)

---

## Pattern 18: Integer to English / Roman Conversions

### Signal
- "Convert integer to English words", "integer to Roman", "Roman to integer"

### Template

```java
// Integer to Roman
public String intToRoman(int num) {
    int[] values =    {1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1};
    String[] syms = {"M","CM","D","CD","C","XC","L","XL","X","IX","V","IV","I"};
    StringBuilder sb = new StringBuilder();
    for (int i = 0; i < values.length; i++) {
        while (num >= values[i]) {
            sb.append(syms[i]);
            num -= values[i];
        }
    }
    return sb.toString();
}

// Roman to Integer
public int romanToInt(String s) {
    Map<Character, Integer> map = Map.of(
        'I',1, 'V',5, 'X',10, 'L',50, 'C',100, 'D',500, 'M',1000);
    int result = 0;
    for (int i = 0; i < s.length(); i++) {
        int val = map.get(s.charAt(i));
        if (i + 1 < s.length() && val < map.get(s.charAt(i + 1))) {
            result -= val; // subtractive case: IV, IX, etc.
        } else {
            result += val;
        }
    }
    return result;
}

// Integer to English Words (0 to 2^31 - 1)
private final String[] ONES = {"","One","Two","Three","Four","Five","Six",
    "Seven","Eight","Nine","Ten","Eleven","Twelve","Thirteen","Fourteen",
    "Fifteen","Sixteen","Seventeen","Eighteen","Nineteen"};
private final String[] TENS = {"","","Twenty","Thirty","Forty","Fifty",
    "Sixty","Seventy","Eighty","Ninety"};
private final String[] THOUSANDS = {"","Thousand","Million","Billion"};

public String numberToWords(int num) {
    if (num == 0) return "Zero";
    StringBuilder sb = new StringBuilder();
    int i = 0;
    while (num > 0) {
        if (num % 1000 != 0) {
            sb.insert(0, helper(num % 1000) + THOUSANDS[i] + " ");
        }
        num /= 1000;
        i++;
    }
    return sb.toString().trim();
}

private String helper(int num) {
    if (num == 0) return "";
    if (num < 20) return ONES[num] + " ";
    if (num < 100) return TENS[num / 10] + " " + helper(num % 10);
    return ONES[num / 100] + " Hundred " + helper(num % 100);
}
```

### Key Insight
- **Roman**: greedy — subtract largest possible symbol value at each step
- **Roman to int**: if current < next, subtract; else add
- **English**: process in groups of 3 digits (thousands, millions, billions)
  - Handle the 1-19 special case (teens), then tens, then hundreds

### Edge Cases
- num = 0 → "Zero" (special case for English)
- Roman: valid range 1-3999
- English: handle spacing carefully, trim trailing spaces

### Complexity
- All conversions: O(1) since input is bounded (int range)
- String building: O(length of output)

---

## Summary Table

| # | Pattern | Time | Space | Key Trick |
|---|---------|------|-------|-----------|
| 1 | GCD/LCM | O(log n) | O(1) | Euclidean reduction |
| 2 | Sieve | O(n log log n) | O(n) | Start from i*i |
| 3 | Fast Pow | O(log b) | O(1) | Binary decomposition of exponent |
| 4 | Mod Arithmetic | O(n) precomp | O(n) | Fermat's inverse, inverse factorial trick |
| 5 | nCr/nPr | O(n) or O(n^2) | O(n) | Pascal's or factorial method |
| 6 | Catalan | O(n) | O(1) | C(2n,n)/(n+1), left*right split |
| 7 | Matrix Expo | O(k^3 log n) | O(k^2) | Companion matrix for recurrence |
| 8 | Factorization | O(sqrt n) | O(log n) | Trial division up to sqrt |
| 9 | CRT | O(k log m) | O(1) | Iteratively combine pairs |
| 10 | Euler Totient | O(sqrt n) | O(1) | phi(n) = n * prod(1-1/p) |
| 11 | Digit Cycles | O(cycle) | O(1) | Floyd's on bounded sequence |
| 12 | Pow(x,n) | O(log n) | O(1) | Cast n to long for MIN_VALUE |
| 13 | Sqrt(x) | O(log x) | O(1) | Binary search or Newton's |
| 14 | Trailing Zeros | O(log n) | O(1) | Count factors of 5 |
| 15 | Weighted Random | O(log n) pick | O(n) | Prefix sum + binary search |
| 16 | Josephus | O(n) | O(1) | J(n,k) = (J(n-1,k)+k)%n |
| 17 | Ugly Numbers | O(n*k) | O(n) | Multi-pointer, advance all matches |
| 18 | Num Conversions | O(1) | O(1) | Greedy decomposition |
