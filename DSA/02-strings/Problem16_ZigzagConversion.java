import java.util.*;

/**
 * Problem 16: Zigzag Conversion (LeetCode 6)
 * 
 * Approach: Simulate rows, toggle direction. O(n) time, O(n) space.
 * 
 * Production Analogy: Like distributing tasks across worker threads in a round-robin
 * pattern that bounces back.
 */
public class Problem16_ZigzagConversion {

    public static String convert(String s, int numRows) {
        if (numRows == 1 || numRows >= s.length()) return s;
        StringBuilder[] rows = new StringBuilder[numRows];
        for (int i = 0; i < numRows; i++) rows[i] = new StringBuilder();
        int row = 0, dir = -1;
        for (char c : s.toCharArray()) {
            rows[row].append(c);
            if (row == 0 || row == numRows - 1) dir = -dir;
            row += dir;
        }
        StringBuilder result = new StringBuilder();
        for (StringBuilder r : rows) result.append(r);
        return result.toString();
    }

    public static void main(String[] args) {
        System.out.println(convert("PAYPALISHIRING", 3)); // "PAHNAPLSIIGYIR"
        System.out.println(convert("PAYPALISHIRING", 4)); // "PINALSIGYAHRPI"
        System.out.println(convert("A", 1));              // "A"
    }
}
