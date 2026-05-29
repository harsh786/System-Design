import java.util.*;
public class Problem28_BucketSortColorSorting {
    /* Sort RGB colors by hue using buckets */
    public int[][] sortByHue(int[][] colors) {
        // colors: [r,g,b]
        List<int[]>[] buckets=new List[360]; for(int i=0;i<360;i++) buckets[i]=new ArrayList<>();
        for(int[] c:colors){ double hue=getHue(c); buckets[(int)hue%360].add(c); }
        int idx=0; for(List<int[]> b:buckets) for(int[] c:b) colors[idx++]=c;
        return colors;
    }
    private double getHue(int[] c){double r=c[0]/255.0,g=c[1]/255.0,b=c[2]/255.0;double max=Math.max(r,Math.max(g,b)),min=Math.min(r,Math.min(g,b));if(max==min) return 0;double h;if(max==r) h=60*(g-b)/(max-min);else if(max==g) h=120+60*(b-r)/(max-min);else h=240+60*(r-g)/(max-min);return h<0?h+360:h;}
    public static void main(String[] args){ int[][] c={{255,0,0},{0,255,0},{0,0,255},{255,255,0}}; new Problem28_BucketSortColorSorting().sortByHue(c); for(int[] x:c) System.out.println(Arrays.toString(x)); }
}
