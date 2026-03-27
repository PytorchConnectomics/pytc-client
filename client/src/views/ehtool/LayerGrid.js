import React from "react";
import { Row, Col, Card, Pagination, Empty, Checkbox, Tag } from "antd";
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  ExclamationCircleOutlined,
} from "@ant-design/icons";

/**
 * Slice Grid Component
 * Displays slices in a grid with thumbnails and classification status
 */
function LayerGrid({
  layers,
  selectedLayers,
  onLayerSelect,
  onLayerClick,
  currentPage,
  totalPages,
  onPageChange,
}) {
  const getClassificationIcon = (classification) => {
    switch (classification) {
      case "correct":
        return (
          <CheckCircleOutlined style={{ color: "#52c41a", fontSize: "20px" }} />
        );
      case "incorrect":
        return (
          <CloseCircleOutlined style={{ color: "#ff4d4f", fontSize: "20px" }} />
        );
      case "unsure":
        return (
          <QuestionCircleOutlined
            style={{ color: "#faad14", fontSize: "20px" }}
          />
        );
      case "error":
      default:
        return (
          <ExclamationCircleOutlined
            style={{ color: "#d9d9d9", fontSize: "20px" }}
          />
        );
    }
  };

  const getClassificationColor = (classification) => {
    switch (classification) {
      case "correct":
        return "#52c41a";
      case "incorrect":
        return "#ff4d4f";
      case "unsure":
        return "#faad14";
      case "error":
      default:
        return "#d9d9d9";
    }
  };

  const getClassificationText = (classification) => {
    switch (classification) {
      case "correct":
        return "Correct";
      case "incorrect":
        return "Incorrect";
      case "unsure":
        return "Unsure";
      case "error":
      default:
        return "Unreviewed";
    }
  };

  if (layers.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100%",
        }}
      >
        <Empty description="No slices to display" />
      </div>
    );
  }

  return (
    <div>
      <Row gutter={[16, 16]}>
        {layers.map((layer) => {
          const isSelected = selectedLayers.includes(layer.id);

          return (
            <Col key={layer.id} xs={24} sm={12} md={8} lg={6}>
              <Card
                hoverable
                style={{
                  border: isSelected
                    ? "2px solid #1677ff"
                    : "1px solid #e5e7eb",
                  boxShadow: isSelected
                    ? "0 0 12px rgba(22, 119, 255, 0.18)"
                    : "0 6px 20px rgba(15, 23, 42, 0.05)",
                  cursor: "pointer",
                  position: "relative",
                  borderRadius: 12,
                }}
                bodyStyle={{ padding: "8px" }}
                onClick={() => onLayerClick && onLayerClick(layer)}
                cover={
                  <div style={{ position: "relative" }}>
                    <div
                      style={{
                        position: "absolute",
                        top: "8px",
                        left: "8px",
                        zIndex: 10,
                        backgroundColor: "rgba(255,255,255,0.9)",
                        borderRadius: "6px",
                        padding: "2px 6px",
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Checkbox
                        checked={isSelected}
                        onChange={() =>
                          onLayerSelect && onLayerSelect(layer.id)
                        }
                      />
                      <Tag color={getClassificationColor(layer.classification)}>
                        {getClassificationText(layer.classification)}
                      </Tag>
                    </div>

                    {layer.image_base64 ? (
                      <div
                        style={{
                          position: "relative",
                          paddingTop: "100%",
                          background: "#000",
                          overflow: "hidden",
                          borderTopLeftRadius: 12,
                          borderTopRightRadius: 12,
                        }}
                      >
                        <img
                          src={layer.image_base64}
                          alt={layer.layer_name}
                          style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            width: "100%",
                            height: "100%",
                            objectFit: "contain",
                          }}
                        />
                        {layer.mask_base64 && (
                          <img
                            src={layer.mask_base64}
                            alt="mask"
                            style={{
                              position: "absolute",
                              top: 0,
                              left: 0,
                              width: "100%",
                              height: "100%",
                              objectFit: "contain",
                              opacity: 0.5,
                              mixBlendMode: "screen",
                            }}
                          />
                        )}
                      </div>
                    ) : (
                      <div
                        style={{
                          paddingTop: "100%",
                          background: "#f3f4f6",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        Loading...
                      </div>
                    )}
                  </div>
                }
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span
                    style={{
                      fontSize: "12px",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {layer.layer_name}
                  </span>
                  {getClassificationIcon(layer.classification)}
                </div>
                <div
                  style={{
                    fontSize: "11px",
                    color: "#6b7280",
                    marginTop: "4px",
                  }}
                >
                  Slice {layer.layer_index + 1}
                </div>
              </Card>
            </Col>
          );
        })}
      </Row>

      {totalPages > 1 && (
        <div
          style={{
            marginTop: "24px",
            display: "flex",
            justifyContent: "center",
          }}
        >
          <Pagination
            current={currentPage}
            total={totalPages * 12} // Approximate total items
            pageSize={12}
            onChange={onPageChange}
            showSizeChanger={false}
            showTotal={(total, range) => `Page ${currentPage} of ${totalPages}`}
          />
        </div>
      )}
    </div>
  );
}

export default LayerGrid;
