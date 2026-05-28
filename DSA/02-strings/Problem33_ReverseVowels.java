import java.util.*;

/**
 * Problem 33: Reverse Vowels of a String (LeetCode 345)
 * 
 * Approach: Two pointers, swap only vowels. O(n) time, O(n) space for char array.
 * 
 * Production Analogy: Like selectively reordering certain priority items in a queue
 * while keeping others in place.
 */
public class Problem33_ReverseVowels {

    public static String reverseVowels(String s) {
        char[] arr = s.toCharArray();
        String vowels = "aeiouAEIOU";
        int l = 0, r = arr.length - 1;
        while (l < r) {
            while (l < r && vowels.indexOf(arr[l]) == -1) l++;
            while (l < r && vowels.indexOf(arr[r]) == -1) r--;
            char tmp = arr[l]; arr[l] = arr[r]; arr[r] = tmp;
            l++; r--;
        }
        return new String(arr);
    }

    public static void main(String[] args) {
        System.out.println(reverseVowels("hello"));   // "holle"
        System.out.println(reverseVowels("leetcode")); // "leotcede"
        System.out.println(reverseVowels("aA"));      // "Aa"
    }
}
