/**
 * Problem: Design Parking System (LeetCode 1603)
 * Approach: Simple counter-based simulation
 * Complexity: O(1) per operation
 * Production Analogy: Resource pool management with type-based allocation
 */
public class Problem09_DesignParkingSystem {
    int[] slots;
    public Problem09_DesignParkingSystem(int big, int medium, int small) {
        slots = new int[]{0, big, medium, small};
    }
    public boolean addCar(int carType) {
        if (slots[carType] > 0) { slots[carType]--; return true; }
        return false;
    }
    public static void main(String[] args) {
        Problem09_DesignParkingSystem p = new Problem09_DesignParkingSystem(1,1,0);
        System.out.println(p.addCar(1)); // true
        System.out.println(p.addCar(2)); // true
        System.out.println(p.addCar(3)); // false
        System.out.println(p.addCar(1)); // false
    }
}
