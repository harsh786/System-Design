import java.util.*;

public class Problem50_RandomWalkSimulation {
    static Random rand = new Random();

    // 1D random walk: return to origin probability
    static double returnProbability1D(int steps, int trials) {
        int returns = 0;
        for (int t = 0; t < trials; t++) {
            int pos = 0;
            for (int i = 0; i < steps; i++) pos += rand.nextBoolean() ? 1 : -1;
            if (pos == 0) returns++;
        }
        return (double) returns / trials;
    }

    // 2D random walk: expected distance from origin
    static double expectedDistance2D(int steps, int trials) {
        double totalDist = 0;
        for (int t = 0; t < trials; t++) {
            int x = 0, y = 0;
            for (int i = 0; i < steps; i++) {
                int dir = rand.nextInt(4);
                if (dir==0) x++; else if(dir==1) x--; else if(dir==2) y++; else y--;
            }
            totalDist += Math.sqrt(x*x + y*y);
        }
        return totalDist / trials;
    }

    public static void main(String[] args) {
        System.out.printf("1D return prob (100 steps): %.4f%n", returnProbability1D(100, 100000));
        System.out.printf("2D expected distance (100 steps): %.2f (theory: ~%.2f)%n",
            expectedDistance2D(100, 100000), Math.sqrt(100));
    }
}
