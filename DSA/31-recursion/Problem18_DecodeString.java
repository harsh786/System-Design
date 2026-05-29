import java.util.*;

public class Problem18_DecodeString {
    static int i = 0;
    public static String decodeString(String s) {
        i = 0;
        return decode(s);
    }
    static String decode(String s) {
        StringBuilder sb = new StringBuilder();
        while (i < s.length() && s.charAt(i) != ']') {
            if (Character.isDigit(s.charAt(i))) {
                int num = 0;
                while (i < s.length() && Character.isDigit(s.charAt(i))) num = num * 10 + (s.charAt(i++) - '0');
                i++; // '['
                String inner = decode(s);
                i++; // ']'
                while (num-- > 0) sb.append(inner);
            } else {
                sb.append(s.charAt(i++));
            }
        }
        return sb.toString();
    }
    public static void main(String[] args) {
        System.out.println(decodeString("3[a2[c]]")); // accaccacc
    }
}
