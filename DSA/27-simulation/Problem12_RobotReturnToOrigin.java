/**
 * Problem: Robot Return to Origin (LeetCode 657)
 * Approach: Track x,y displacement
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Net displacement tracking in logistics routing
 */
public class Problem12_RobotReturnToOrigin {
    public boolean judgeCircle(String moves) {
        int x=0, y=0;
        for (char c : moves.toCharArray()) {
            if (c=='U') y++; else if (c=='D') y--;
            else if (c=='L') x--; else x++;
        }
        return x==0 && y==0;
    }
    public static void main(String[] args) {
        System.out.println(new Problem12_RobotReturnToOrigin().judgeCircle("UD")); // true
        System.out.println(new Problem12_RobotReturnToOrigin().judgeCircle("LL")); // false
    }
}
