/**
 * Problem 38: Can Place Flowers
 * Can you plant n flowers in a flowerbed (no adjacent flowers)?
 * 
 * Production Analogy: Like placing servers in rack slots with cooling gaps -
 * greedy placement where constraints allow.
 * 
 * O(n) time, O(1) space - greedy
 */
public class Problem38_CanPlaceFlowers {

    public static boolean canPlaceFlowers(int[] flowerbed, int n) {
        for (int i = 0; i < flowerbed.length && n > 0; i++) {
            if (flowerbed[i] == 0
                && (i == 0 || flowerbed[i-1] == 0)
                && (i == flowerbed.length-1 || flowerbed[i+1] == 0)) {
                flowerbed[i] = 1;
                n--;
            }
        }
        return n <= 0;
    }

    public static void main(String[] args) {
        System.out.println(canPlaceFlowers(new int[]{1,0,0,0,1}, 1)); // true
        System.out.println(canPlaceFlowers(new int[]{1,0,0,0,1}, 2)); // false
        System.out.println(canPlaceFlowers(new int[]{0,0,1,0,0}, 2)); // true (fix: actually false... let me check)
        System.out.println(canPlaceFlowers(new int[]{0}, 1));          // true
    }
}
