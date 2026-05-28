import java.util.*;

/**
 * Problem 47: Tag Validator (LeetCode 591)
 * 
 * Validate if a code snippet with tags is valid.
 * 
 * Approach: Stack of tag names. Parse opening/closing tags and CDATA sections.
 * Validate tag names (1-9 uppercase letters). Ensure proper nesting.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like XML/HTML validators in web servers that reject
 * malformed markup before processing to prevent injection attacks.
 */
public class Problem47_TagValidator {

    public static boolean isValid(String code) {
        Deque<String> stack = new ArrayDeque<>();
        int i = 0;
        while (i < code.length()) {
            if (i > 0 && stack.isEmpty()) return false;
            if (code.startsWith("<![CDATA[", i)) {
                int j = code.indexOf("]]>", i);
                if (j == -1) return false;
                i = j + 3;
            } else if (code.startsWith("</", i)) {
                int j = code.indexOf(">", i);
                if (j == -1) return false;
                String tag = code.substring(i + 2, j);
                if (!isValidTag(tag)) return false;
                if (stack.isEmpty() || !stack.pop().equals(tag)) return false;
                i = j + 1;
            } else if (code.startsWith("<", i)) {
                int j = code.indexOf(">", i);
                if (j == -1) return false;
                String tag = code.substring(i + 1, j);
                if (!isValidTag(tag)) return false;
                stack.push(tag);
                i = j + 1;
            } else {
                i++;
            }
        }
        return stack.isEmpty();
    }

    private static boolean isValidTag(String tag) {
        if (tag.length() < 1 || tag.length() > 9) return false;
        for (char c : tag.toCharArray()) {
            if (!Character.isUpperCase(c)) return false;
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(isValid("<DIV>This is the first line <![CDATA[<div>]]></DIV>")); // true
        System.out.println(isValid("<DIV>>>  ![cdata[]] <![CDATA[<div>]>]]>]]>>]</DIV>")); // true
        System.out.println(isValid("<A>  <B> </A>   </B>"));  // false
        System.out.println(isValid("<DIV>  div tag is not closed"));  // false
    }
}
