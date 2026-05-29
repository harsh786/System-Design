import java.util.*;

public class Problem25_FoodRatingsSystem {
    // LC 2353: Design food rating system with changeRating and highestRated
    Map<String, String> foodCuisine;
    Map<String, Integer> foodRating;
    Map<String, TreeMap<Integer, TreeSet<String>>> cuisineRatings;

    public Problem25_FoodRatingsSystem(String[] foods, String[] cuisines, int[] ratings) {
        foodCuisine = new HashMap<>();
        foodRating = new HashMap<>();
        cuisineRatings = new HashMap<>();
        for (int i = 0; i < foods.length; i++) {
            foodCuisine.put(foods[i], cuisines[i]);
            foodRating.put(foods[i], ratings[i]);
            cuisineRatings.computeIfAbsent(cuisines[i], k -> new TreeMap<>(Collections.reverseOrder()))
                .computeIfAbsent(ratings[i], k -> new TreeSet<>()).add(foods[i]);
        }
    }

    public void changeRating(String food, int newRating) {
        String cuisine = foodCuisine.get(food);
        int oldRating = foodRating.get(food);
        TreeMap<Integer, TreeSet<String>> tm = cuisineRatings.get(cuisine);
        tm.get(oldRating).remove(food);
        if (tm.get(oldRating).isEmpty()) tm.remove(oldRating);
        tm.computeIfAbsent(newRating, k -> new TreeSet<>()).add(food);
        foodRating.put(food, newRating);
    }

    public String highestRated(String cuisine) {
        return cuisineRatings.get(cuisine).firstEntry().getValue().first();
    }

    public static void main(String[] args) {
        Problem25_FoodRatingsSystem sys = new Problem25_FoodRatingsSystem(
            new String[]{"kimchi","miso","sushi","moussaka","ramen","bulgogi"},
            new String[]{"korean","japanese","japanese","greek","japanese","korean"},
            new int[]{9,12,8,15,14,7});
        System.out.println(sys.highestRated("korean"));   // kimchi
        System.out.println(sys.highestRated("japanese")); // ramen
        sys.changeRating("sushi", 16);
        System.out.println(sys.highestRated("japanese")); // sushi
    }
}
