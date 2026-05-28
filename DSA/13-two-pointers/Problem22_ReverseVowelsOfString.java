/**
 * Problem 22: Reverse Vowels of a String
 * 
 * Reverse only the vowels in a string.
 * 
 * Approach: Two pointers from ends, swap when both point to vowels.
 * Time: O(n), Space: O(n) for char array
 * 
 * Production Analogy: Like selectively reordering priority messages in a
 * queue while leaving normal messages in place.
 */
public class Problem22_ReverseVowelsOfString {
    public static String reverseVowels(String s) {
        char[] arr = s.toCharArray();
        int left = 0, right = arr.length - 1;
        String vowels = "aeiouAEIOU";
        while (left < right) {
            while (left < right && vowels.indexOf(arr[left]) == -1) left++;
            while (left < right && vowels.indexOf(arr[right]) == -1) right--;
            char tmp = arr[left]; arr[left] = arr[right]; arr[right] = tmp;
            left++; right--;
        }
        return new String(arr);
    }

    public static void main(String[] args) {
        System.out.println(reverseVowels("hello")); // holle
        System.out.println(reverseVowels("leetcode")); // leotcede
        System.out.println(reverseVowels("aA")); // Aa
    }
}
