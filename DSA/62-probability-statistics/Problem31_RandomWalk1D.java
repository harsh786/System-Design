import java.util.*;

public class Problem31_RandomWalk1D {
    public int[] simulate(int steps) {
        Random rand = new Random();
        int[] path = new int[steps + 1];
        for (int i = 1; i <= steps; i++) path[i] = path[i-1] + (rand.nextBoolean() ? 1 : -1);
        return path;
    }

    public static void main(String[] args) {
        Problem31_RandomWalk1D sol = new Problem31_RandomWalk1D();
        int[] path = sol.simulate(20);
        System.out.println(Arrays.toString(path));
    }
}
