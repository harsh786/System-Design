import java.util.*;

/**
 * Problem 26: Design Parking System
 * 
 * API Contract:
 * - addCar(carType): 1=big, 2=medium, 3=small. Return true if space available.
 * 
 * Complexity: O(1)
 * Data Structure: Array of 3 counters
 * 
 * Production Analogy: Resource pool management, connection pooling,
 * cloud instance quota enforcement, parking garage IoT systems
 */
public class Problem26_DesignParkingSystem {

    static class ParkingSystem {
        private int[] slots;

        public ParkingSystem(int big, int medium, int small) {
            slots = new int[]{0, big, medium, small};
        }

        public boolean addCar(int carType) {
            if (slots[carType] > 0) { slots[carType]--; return true; }
            return false;
        }
    }

    public static void main(String[] args) {
        ParkingSystem ps = new ParkingSystem(1, 1, 0);
        assert ps.addCar(1);  // big
        assert !ps.addCar(1); // full
        assert ps.addCar(2);  // medium
        assert !ps.addCar(3); // no small slots
        assert !ps.addCar(2); // medium full

        System.out.println("All tests passed!");
    }
}
