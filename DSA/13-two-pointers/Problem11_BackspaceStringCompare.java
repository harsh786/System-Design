/**
 * Problem 11: Backspace String Compare
 * 
 * Given two strings with '#' as backspace, check if they are equal.
 * 
 * Approach: Traverse from end, skip characters after '#', compare.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like comparing two terminal session outputs where
 * users typed corrections - you must resolve delete operations before comparing.
 */
public class Problem11_BackspaceStringCompare {
    public static boolean backspaceCompare(String s, String t) {
        int i = s.length() - 1, j = t.length() - 1;
        while (i >= 0 || j >= 0) {
            i = getNextValid(s, i);
            j = getNextValid(t, j);
            if (i >= 0 && j >= 0 && s.charAt(i) != t.charAt(j)) return false;
            if ((i >= 0) != (j >= 0)) return false;
            i--; j--;
        }
        return true;
    }

    private static int getNextValid(String s, int idx) {
        int skip = 0;
        while (idx >= 0) {
            if (s.charAt(idx) == '#') { skip++; idx--; }
            else if (skip > 0) { skip--; idx--; }
            else break;
        }
        return idx;
    }

    public static void main(String[] args) {
        System.out.println(backspaceCompare("ab#c", "ad#c")); // true
        System.out.println(backspaceCompare("ab##", "c#d#")); // true
        System.out.println(backspaceCompare("a#c", "b")); // false
    }
}
