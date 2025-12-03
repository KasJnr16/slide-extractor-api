package com.example.converter;

import org.apache.poi.hslf.usermodel.*;
import java.io.FileInputStream;

public class PptTextExtractor {

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            System.out.println("Usage: java -jar ppt-text-extractor.jar input.ppt");
            return;
        }

        String inputPath = args[0];
        HSLFSlideShow ppt = new HSLFSlideShow(new FileInputStream(inputPath));

        int slideNum = 1;
        for (HSLFSlide slide : ppt.getSlides()) {
            System.out.println("--- Slide " + slideNum + " ---");

            for (HSLFShape shape : slide.getShapes()) {
                extractShapeText(shape);
            }

            slideNum++;
            System.out.println();
        }

        ppt.close();
    }

    private static void extractShapeText(HSLFShape shape) {
        // 1️⃣ Text shapes
        if (shape instanceof HSLFTextShape) {
            HSLFTextShape textShape = (HSLFTextShape) shape;
            String text = textShape.getText();
            if (text != null && !text.isEmpty()) {
                System.out.println(text);
            }
        }

        // 2️⃣ Tables
        if (shape instanceof HSLFTable) {
            HSLFTable table = (HSLFTable) shape;
            int rows = table.getNumberOfRows();
            int cols = table.getNumberOfColumns();

            for (int r = 0; r < rows; r++) {
                for (int c = 0; c < cols; c++) {
                    HSLFTableCell cell = table.getCell(r, c);
                    if (cell != null) {
                        // Get the text from the list of paragraphs
                        String text = HSLFTextParagraph.getText(cell.getTextParagraphs());
                        if (text != null && !text.isEmpty()) {
                            System.out.println(text);
                        }

                    }
                }
            }
        }

        // 3️⃣ Grouped shapes (recursively)
        if (shape instanceof HSLFGroupShape) {
            HSLFGroupShape group = (HSLFGroupShape) shape;
            for (HSLFShape subShape : group.getShapes()) {
                extractShapeText(subShape);
            }
        }
    }
}
