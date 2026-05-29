public class Problem47_MultinomialCoefficient {
    // Multinomial(n; k1,k2,...,km) = n! / (k1! * k2! * ... * km!)
    public long multinomial(int n, int[] groups) {
        long result = 1;
        int remaining = n;
        for (int g : groups) {
            result *= binomial(remaining, g);
            remaining -= g;
        }
        return result;
    }

    private long binomial(int n, int r) {
        if (r > n - r) r = n - r;
        long res = 1;
        for (int i = 0; i < r; i++) res = res * (n - i) / (i + 1);
        return res;
    }

    public static void main(String[] args) {
        // Ways to arrange "MISSISSIPPI" = 11!/(1!4!4!2!) = 34650
        System.out.println(new Problem47_MultinomialCoefficient().multinomial(11, new int[]{1,4,4,2}));
    }
}
