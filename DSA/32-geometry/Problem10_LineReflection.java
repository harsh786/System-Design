import java.util.*;

public class Problem10_LineReflection {
    public static boolean isReflected(int[][] points) {
        Set<String> set = new HashSet<>();
        int minX = Integer.MAX_VALUE, maxX = Integer.MIN_VALUE;
        for (int[] p : points) { minX = Math.min(minX, p[0]); maxX = Math.max(maxX, p[0]); set.add(p[0] + "," + p[1]); }
        int sum = minX + maxX;
        for (int[] p : points) if (!set.contains((sum - p[0]) + "," + p[1])) return false;
        return true;
    }
    public static void main(String[] args) {
        System.out.println(isReflected(new int[][]{{1,1},{-1,1}})); // true
        System.out.println(isReflected(new int[][]{{1,1},{-1,-1}})); // false
    }
}
