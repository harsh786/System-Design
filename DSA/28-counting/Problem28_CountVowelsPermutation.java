/**
 * Problem: Count Vowels Permutation (LeetCode 1220)
 * Approach: DP with transition rules for each vowel
 * Complexity: O(n) time, O(1) space
 * Production Analogy: State machine transition counting in protocol analysis
 */
public class Problem28_CountVowelsPermutation {
    public int countVowelPermutation(int n) {
        long MOD = 1_000_000_007;
        long a=1,e=1,i=1,o=1,u=1;
        for (int k = 1; k < n; k++) {
            long na = (e+i+u)%MOD, ne = (a+i)%MOD, ni = (e+o)%MOD, no = i%MOD, nu = (i+o)%MOD;
            a=na; e=ne; i=ni; o=no; u=nu;
        }
        return (int)((a+e+i+o+u)%MOD);
    }
    public static void main(String[] args) {
        System.out.println(new Problem28_CountVowelsPermutation().countVowelPermutation(5)); // 68
    }
}
