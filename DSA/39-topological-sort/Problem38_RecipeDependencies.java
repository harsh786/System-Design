import java.util.*;

/**
 * Problem: Recipe Dependencies
 * Find all recipes that can be made given available supplies and recipe dependencies.
 *
 * Approach: Topological sort treating supplies as nodes with 0 in-degree
 *
 * Time Complexity: O(V + E)
 * Space Complexity: O(V + E)
 *
 * Production Analogy: Determining which features can be enabled given available infrastructure.
 */
public class Problem38_RecipeDependencies {

    public List<String> findAllRecipes(String[] recipes, List<List<String>> ingredients, String[] supplies) {
        Map<String, List<String>> graph = new HashMap<>();
        Map<String, Integer> inDeg = new HashMap<>();
        Set<String> recipeSet = new HashSet<>(Arrays.asList(recipes));

        for (String r : recipes) { inDeg.put(r, 0); graph.putIfAbsent(r, new ArrayList<>()); }

        for (int i = 0; i < recipes.length; i++) {
            for (String ing : ingredients.get(i)) {
                graph.computeIfAbsent(ing, k -> new ArrayList<>()).add(recipes[i]);
                inDeg.merge(recipes[i], 1, Integer::sum);
            }
        }

        Queue<String> q = new LinkedList<>(Arrays.asList(supplies));
        List<String> result = new ArrayList<>();
        while (!q.isEmpty()) {
            String item = q.poll();
            if (recipeSet.contains(item)) result.add(item);
            for (String nei : graph.getOrDefault(item, Collections.emptyList()))
                if (inDeg.merge(nei, -1, Integer::sum) == 0) q.offer(nei);
        }
        return result;
    }

    public static void main(String[] args) {
        Problem38_RecipeDependencies solver = new Problem38_RecipeDependencies();
        List<List<String>> ings = Arrays.asList(Arrays.asList("yeast","flour"), Arrays.asList("bread","meat"));
        System.out.println(solver.findAllRecipes(new String[]{"bread","sandwich"}, ings, new String[]{"yeast","flour","meat"}));
    }
}
