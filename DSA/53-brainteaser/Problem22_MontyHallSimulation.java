import java.util.*;

public class Problem22_MontyHallSimulation {
    static double simulate(boolean switchDoor, int trials) {
        Random rand = new Random(42);
        int wins = 0;
        for (int t = 0; t < trials; t++) {
            int car = rand.nextInt(3);
            int pick = rand.nextInt(3);
            // Host opens a goat door (not car, not pick)
            if (switchDoor) { if (pick != car) wins++; } // switching wins when initial pick was wrong
            else { if (pick == car) wins++; }
        }
        return (double) wins / trials;
    }
    
    public static void main(String[] args) {
        System.out.printf("Stay: %.4f%n", simulate(false, 100000)); // ~0.33
        System.out.printf("Switch: %.4f%n", simulate(true, 100000)); // ~0.67
    }
}
