import java.util.*;

public class Problem14_BirthdayParadox {
    public double simulate(int people, int trials) {
        Random rand = new Random();
        int collisions = 0;
        for (int t = 0; t < trials; t++) {
            Set<Integer> bdays = new HashSet<>();
            boolean found = false;
            for (int i = 0; i < people; i++) {
                int b = rand.nextInt(365);
                if (!bdays.add(b)) { found = true; break; }
            }
            if (found) collisions++;
        }
        return (double) collisions / trials;
    }

    public static void main(String[] args) {
        Problem14_BirthdayParadox sol = new Problem14_BirthdayParadox();
        System.out.println("23 people collision prob: " + sol.simulate(23, 100000));
        System.out.println("50 people collision prob: " + sol.simulate(50, 100000));
    }
}
