public class Problem21_SelfCrossing {
    public static boolean isSelfCrossing(int[] distance) {
        for (int i = 3; i < distance.length; i++) {
            if (distance[i] >= distance[i-2] && distance[i-1] <= distance[i-3]) return true;
            if (i >= 4 && distance[i-1] == distance[i-3] && distance[i] + distance[i-4] >= distance[i-2]) return true;
            if (i >= 5 && distance[i-2] >= distance[i-4] && distance[i] + distance[i-4] >= distance[i-2] && distance[i-1] <= distance[i-3] && distance[i-1] + distance[i-5] >= distance[i-3]) return true;
        }
        return false;
    }
    public static void main(String[] args) {
        System.out.println(isSelfCrossing(new int[]{2,1,1,2})); // true
        System.out.println(isSelfCrossing(new int[]{1,2,3,4})); // false
    }
}
