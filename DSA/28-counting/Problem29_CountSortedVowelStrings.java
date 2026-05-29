/**
 * Problem: Count Sorted Vowel Strings (LeetCode 1641)
 * Approach: Combinatorics - stars and bars: C(n+4, 4)
 * Complexity: O(1) time, O(1) space
 * Production Analogy: Combinatorial enumeration for configuration space analysis
 */
public class Problem29_CountSortedVowelStrings {
    public int countVowelStrings(int n) {
        // C(n+4, 4) = (n+4)*(n+3)*(n+2)*(n+1)/24
        return (n+4)*(n+3)*(n+2)*(n+1)/24;
    }
    public static void main(String[] args) {
        System.out.println(new Problem29_CountSortedVowelStrings().countVowelStrings(2)); // 15
        System.out.println(new Problem29_CountSortedVowelStrings().countVowelStrings(33)); // 66045
    }
}
