public class Problem48_SubsetEnumerationTricks {
    public static void main(String[] args) {
        int mask = 0b1101; // set = {0, 2, 3}
        System.out.println("All subsets of mask " + Integer.toBinaryString(mask) + ":");
        // Enumerate all subsets of a given mask
        for (int sub = mask; sub > 0; sub = (sub - 1) & mask)
            System.out.println("  " + Integer.toBinaryString(sub));
        System.out.println("  0");

        // Enumerate all supersets of mask in universe of size n
        int n = 4, universe = (1 << n) - 1;
        System.out.println("All supersets of " + Integer.toBinaryString(mask) + " in " + n + "-bit universe:");
        int complement = universe ^ mask;
        for (int sup = complement; ; sup = (sup - 1) & complement) {
            System.out.println("  " + Integer.toBinaryString(sup | mask));
            if (sup == 0) break;
        }

        // Lowest set bit
        System.out.println("Lowest set bit of " + mask + ": " + (mask & -mask));
        // Remove lowest set bit
        System.out.println("Remove lowest: " + Integer.toBinaryString(mask & (mask - 1)));
    }
}
