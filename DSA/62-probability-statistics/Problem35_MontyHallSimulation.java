import java.util.*;

public class Problem35_MontyHallSimulation {
    public double simulate(boolean switchDoor, int trials) {
        Random rand = new Random();
        int wins = 0;
        for (int t = 0; t < trials; t++) {
            int car = rand.nextInt(3), choice = rand.nextInt(3);
            if (switchDoor) { if (choice != car) wins++; }
            else { if (choice == car) wins++; }
        }
        return (double) wins / trials;
    }

    public static void main(String[] args) {
        Problem35_MontyHallSimulation sol = new Problem35_MontyHallSimulation();
        System.out.printf("Stay: %.4f, Switch: %.4f%n", sol.simulate(false, 1000000), sol.simulate(true, 1000000));
    }
}
