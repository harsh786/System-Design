import java.util.*;

public class Problem12_NumberOfBoomerangs {
    public static int numberOfBoomerangs(int[][] points) {
        int count = 0;
        for (int[] p : points) {
            Map<Integer, Integer> map = new HashMap<>();
            for (int[] q : points) {
                int d = (p[0]-q[0])*(p[0]-q[0]) + (p[1]-q[1])*(p[1]-q[1]);
                map.merge(d, 1, Integer::sum);
            }
            for (int v : map.values()) count += v * (v - 1);
        }
        return count;
    }
    public static void main(String[] args) {
        System.out.println(numberOfBoomerangs(new int[][]{{0,0},{1,0},{2,0}})); // 2
    }
}
