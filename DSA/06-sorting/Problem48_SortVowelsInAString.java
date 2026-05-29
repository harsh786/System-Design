import java.util.*;

/**
 * Problem 48: Sort Vowels in a String
 * 
 * Sort only the vowels in the string while keeping consonants in place.
 * 
 * Approach: Collect vowels, sort them, place back at vowel positions.
 * Time Complexity: O(n log n) for sorting vowels
 * Space Complexity: O(n)
 * 
 * Production Analogy: Selective field sorting in structured records - sort specific columns
 * while maintaining row associations for other columns.
 */
public class Problem48_SortVowelsInAString {
    
    public String sortVowels(String s) {
        char[] chars = s.toCharArray();
        List<Character> vowels = new ArrayList<>();
        
        for (char c : chars) {
            if (isVowel(c)) vowels.add(c);
        }
        Collections.sort(vowels);
        
        int vi = 0;
        for (int i = 0; i < chars.length; i++) {
            if (isVowel(chars[i])) {
                chars[i] = vowels.get(vi++);
            }
        }
        return new String(chars);
    }
    
    private boolean isVowel(char c) {
        return "aeiouAEIOU".indexOf(c) != -1;
    }
    
    public static void main(String[] args) {
        Problem48_SortVowelsInAString sol = new Problem48_SortVowelsInAString();
        
        System.out.println("Test 1: " + sol.sortVowels("lEetcOde")); // "lEOtcede"
        System.out.println("Test 2: " + sol.sortVowels("lYmpH")); // "lYmpH" (no vowels)
        System.out.println("Test 3: " + sol.sortVowels("aeiou")); // "aeiou"
        System.out.println("Test 4: " + sol.sortVowels("AEIOU")); // "AEIOU"
    }
}
