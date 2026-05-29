import java.util.*;

public class Problem32_RandomWalk2D {
    public double expectedDistance(int steps, int trials) {
        Random rand = new Random();
        double totalDist = 0;
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        for (int t = 0; t < trials; t++) {
            int x = 0, y = 0;
            for (int s = 0; s < steps; s++) { int[] d = dirs[rand.nextInt(4)]; x += d[0]; y += d[1]; }
            totalDist += Math.sqrt(x*x + y*y);
        }
        return totalDist / trials;
    }

    public static void main(String[] args) {
        Problem32_RandomWalk2D sol = new Problem32_RandomWalk2D();
        System.out.printf("Expected distance after 100 steps: %.3f (theory ~%.3f)%n", sol.expectedDistance(100, 100000), Math.sqrt(100)*0.886);
    }
}
