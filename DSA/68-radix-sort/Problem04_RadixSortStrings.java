import java.util.*;

/**
 * Problem 4: Radix Sort for Strings
 * 
 * MSD radix sort is natural for strings:
 * - Process character by character from left to right
 * - Recursively sort each bucket by next character
 * - Handle variable-length strings (shorter strings come first)
 * 
 * Time: O(W * n) where W = max string length
 * Space: O(n + R) where R = alphabet size (256 for ASCII)
 * 
 * This is essentially the algorithm used by many string sorting libraries.
 */
public class Problem04_RadixSortStrings {

    private static final int R = 256; // ASCII alphabet size

    public static void msdRadixSort(String[] arr) {
        String[] aux = new String[arr.length];
        msdSort(arr, aux, 0, arr.length - 1, 0);
    }

    private static void msdSort(String[] arr, String[] aux, int lo, int hi, int d) {
        if (lo >= hi) return;
        
        // Small subarrays: use insertion sort (cutoff)
        if (hi - lo < 15) {
            insertionSort(arr, lo, hi, d);
            return;
        }
        
        int[] count = new int[R + 2]; // +1 for end-of-string, +1 for cumulative
        
        // Count frequencies (charAt returns -1 for end-of-string)
        for (int i = lo; i <= hi; i++) {
            count[charAt(arr[i], d) + 2]++;
        }
        
        // Compute cumulates
        for (int r = 0; r < R + 1; r++) {
            count[r + 1] += count[r];
        }
        
        // Distribute
        for (int i = lo; i <= hi; i++) {
            aux[count[charAt(arr[i], d) + 1]++] = arr[i];
        }
        
        // Copy back
        for (int i = lo; i <= hi; i++) {
            arr[i] = aux[i - lo];
        }
        
        // Recursively sort each character bucket
        for (int r = 0; r < R; r++) {
            msdSort(arr, aux, lo + count[r], lo + count[r + 1] - 1, d + 1);
        }
    }

    private static int charAt(String s, int d) {
        return d < s.length() ? s.charAt(d) : -1; // -1 for end-of-string
    }

    private static void insertionSort(String[] arr, int lo, int hi, int d) {
        for (int i = lo + 1; i <= hi; i++) {
            String temp = arr[i];
            int j = i;
            while (j > lo && compareFrom(arr[j-1], temp, d) > 0) {
                arr[j] = arr[j-1];
                j--;
            }
            arr[j] = temp;
        }
    }

    private static int compareFrom(String a, String b, int d) {
        int minLen = Math.min(a.length(), b.length());
        for (int i = d; i < minLen; i++) {
            if (a.charAt(i) != b.charAt(i)) return a.charAt(i) - b.charAt(i);
        }
        return a.length() - b.length();
    }

    public static void main(String[] args) {
        String[] words = {"banana", "apple", "cherry", "date", "apricot", 
                         "blueberry", "avocado", "blackberry", "a", "ap"};
        
        System.out.println("MSD Radix Sort for Strings");
        System.out.println("Before: " + Arrays.toString(words));
        
        msdRadixSort(words);
        
        System.out.println("After:  " + Arrays.toString(words));
        
        // Verify
        for (int i = 1; i < words.length; i++) {
            assert words[i].compareTo(words[i-1]) >= 0 : "Not sorted at " + i;
        }
        System.out.println("PASS");
    }
}
