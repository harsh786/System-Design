import java.util.*;

public class Problem33_GamblersRuin {
    public double ruinProbability(int initial, int goal, double p) {
        if (p == 0.5) return 1.0 - (double)initial / goal;
        double r = (1-p)/p;
        return (Math.pow(r, initial) - Math.pow(r, goal)) / (1 - Math.pow(r, goal));
    }

    public double simulate(int initial, int goal, double p, int trials) {
        Random rand = new Random();
        int ruins = 0;
        for (int t = 0; t < trials; t++) {
            int money = initial;
            while (money > 0 && money < goal) money += rand.nextDouble() < p ? 1 : -1;
            if (money == 0) ruins++;
        }
        return (double) ruins / trials;
    }

    public static void main(String[] args) {
        Problem33_GamblersRuin sol = new Problem33_GamblersRuin();
        System.out.printf("Ruin prob (i=5,g=10,p=0.5): theory=%.4f sim=%.4f%n", sol.ruinProbability(5,10,0.5), sol.simulate(5,10,0.5,100000));
    }
}
