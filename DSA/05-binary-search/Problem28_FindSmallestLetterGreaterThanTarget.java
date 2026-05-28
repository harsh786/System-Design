/**
 * Problem 28: Find Smallest Letter Greater Than Target
 * 
 * Sorted char array (wraps around). Find smallest char strictly greater than target.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Finding next available slot in a circular scheduling buffer.
 */
public class Problem28_FindSmallestLetterGreaterThanTarget {
    public static char nextGreatestLetter(char[] letters, char target) {
        int lo = 0, hi = letters.length;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (letters[mid] <= target) lo = mid + 1;
            else hi = mid;
        }
        return letters[lo % letters.length]; // wrap around
    }

    public static void main(String[] args) {
        System.out.println(nextGreatestLetter(new char[]{'c','f','j'}, 'a')); // c
        System.out.println(nextGreatestLetter(new char[]{'c','f','j'}, 'c')); // f
        System.out.println(nextGreatestLetter(new char[]{'c','f','j'}, 'j')); // c (wrap)
        System.out.println(nextGreatestLetter(new char[]{'a','b'}, 'z'));      // a (wrap)
    }
}
