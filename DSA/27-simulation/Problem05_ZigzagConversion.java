/**
 * Problem: Zigzag Conversion (LeetCode 6)
 * Approach: Simulate row assignment with direction toggle
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Data interleaving in multiplexed communication channels
 */
public class Problem05_ZigzagConversion {
    public String convert(String s, int numRows) {
        if (numRows==1) return s;
        StringBuilder[] rows = new StringBuilder[numRows];
        for (int i=0; i<numRows; i++) rows[i]=new StringBuilder();
        int cur=0, dir=1;
        for (char c : s.toCharArray()) {
            rows[cur].append(c);
            if (cur==0) dir=1;
            else if (cur==numRows-1) dir=-1;
            cur+=dir;
        }
        StringBuilder res = new StringBuilder();
        for (StringBuilder r : rows) res.append(r);
        return res.toString();
    }
    public static void main(String[] args) {
        System.out.println(new Problem05_ZigzagConversion().convert("PAYPALISHIRING", 3)); // PAHNAPLSIIGYIR
    }
}
