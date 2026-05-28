import java.util.*;

/**
 * Problem 12: Encode and Decode Strings (LeetCode 271)
 * 
 * Design an algorithm to encode a list of strings to a single string and decode it back.
 * 
 * Approach: Use length-prefixed encoding: "len#string". O(n) time for both encode/decode.
 * 
 * Production Analogy: Like HTTP chunked transfer encoding - each chunk is prefixed with
 * its size so the receiver knows exactly how many bytes to read.
 */
public class Problem12_EncodeDecodeStrings {

    public static String encode(List<String> strs) {
        StringBuilder sb = new StringBuilder();
        for (String s : strs) {
            sb.append(s.length()).append('#').append(s);
        }
        return sb.toString();
    }

    public static List<String> decode(String s) {
        List<String> result = new ArrayList<>();
        int i = 0;
        while (i < s.length()) {
            int j = s.indexOf('#', i);
            int len = Integer.parseInt(s.substring(i, j));
            result.add(s.substring(j + 1, j + 1 + len));
            i = j + 1 + len;
        }
        return result;
    }

    public static void main(String[] args) {
        List<String> input = Arrays.asList("Hello", "World", "", "foo#bar");
        String encoded = encode(input);
        System.out.println("Encoded: " + encoded);
        System.out.println("Decoded: " + decode(encoded));
        
        List<String> empty = Arrays.asList();
        System.out.println("Empty: " + decode(encode(empty)));
    }
}
